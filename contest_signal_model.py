import os
import json
import hashlib
import pandas as pd
import numpy as np

FIXTURE_BLOCKED_WARNINGS = []

def is_test_mode_active():
    import sys
    import os
    env_mode = os.environ.get("PPG_RUN_MODE")
    if env_mode == "TEST_MODE":
        return True
    if env_mode == "PRODUCTION_MODE":
        return False
    if any("run_audit_tests" in arg or "test_streamlit_app" in arg for arg in sys.argv):
        return True
    return False

def is_fixture_path(path):
    if not path:
        return False
    normalized = str(path).replace("\\", "/").lower()
    return "tests/" in normalized or "tests/fixtures/" in normalized

def calculate_file_hash(file_path):
    if not os.path.exists(file_path):
        return ""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception:
        return ""

def calculate_precinct_contest_signals(
    production_df,
    contest_library,
    column_classification_matrix,
    current_campaign_profile
):
    """
    Computes precinct-level contest signals based on user-defined classification matrix,
    library configuration, and current campaign profile.
    
    Returns a precinct-contest matrix DataFrame.
    """
    precincts = production_df["PrecinctName"].unique()
    
    # Load crosswalk mapping if any contest uses it
    crosswalk_path = "outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk.csv"
    cross_map = {}
    if os.path.exists(crosswalk_path):
        try:
            df_cross = pd.read_csv(crosswalk_path)
            for _, r in df_cross.iterrows():
                vp = str(r.get("Voter_PrecinctName", "")).strip()
                if vp.endswith(".0"):
                    vp = vp[:-2]
                if vp:
                    cross_map[vp.upper()] = r
        except Exception:
            pass

    records = []
    
    # Iterate over each contest in the library
    for contest in contest_library:
        contest_id = contest.get("contest_id")
        contest_name = contest.get("contest_name")
        contest_type = contest.get("contest_type")
        source_file = contest.get("source_file")
        precinct_column = contest.get("precinct_column", "Precinct")
        uses_crosswalk = contest.get("uses_official_crosswalk", False)
        contest_weight = float(contest.get("contest_weight", 1.0))
        confidence_weight = float(contest.get("confidence_weight", 1.0))
        enabled = contest.get("enabled", True)
        
        # Resolve the crosswalk map for this specific contest
        contest_cross_map = {}
        if uses_crosswalk:
            reg_pdf = contest.get("crosswalk_reg_to_voting_file", "")
            voting_pdf = contest.get("crosswalk_voting_to_reg_file", "")
            
            reg_pdf_path = ""
            if reg_pdf:
                if os.path.exists(reg_pdf):
                    reg_pdf_path = reg_pdf
                elif os.path.exists(os.path.join("data", os.path.basename(reg_pdf))):
                    reg_pdf_path = os.path.join("data", os.path.basename(reg_pdf))
                    
            voting_pdf_path = ""
            if voting_pdf:
                if os.path.exists(voting_pdf):
                    voting_pdf_path = voting_pdf
                elif os.path.exists(os.path.join("data", os.path.basename(voting_pdf))):
                    voting_pdf_path = os.path.join("data", os.path.basename(voting_pdf))
                    
            if reg_pdf_path and voting_pdf_path:
                contest_cw_path = f"outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk_{contest_id}.csv"
                if not os.path.exists(contest_cw_path):
                    try:
                        from scratch.build_precinct_crosswalk import build_canonical_crosswalk
                        build_canonical_crosswalk(reg_pdf_path, voting_pdf_path, contest_cw_path)
                    except Exception as e:
                        print(f"Error building custom crosswalk: {e}")
                
                if os.path.exists(contest_cw_path):
                    try:
                        df_cross = pd.read_csv(contest_cw_path)
                        for _, r in df_cross.iterrows():
                            vp = str(r.get("Voter_PrecinctName", "")).strip()
                            if vp.endswith(".0"):
                                vp = vp[:-2]
                            if vp:
                                contest_cross_map[vp.upper()] = r
                    except Exception:
                        pass
            
            if not contest_cross_map:
                contest_cross_map = cross_map
        
        # Load contest data
        if is_fixture_path(source_file) and not is_test_mode_active():
            if "fixture_contest_blocked_from_non_test_run" not in FIXTURE_BLOCKED_WARNINGS:
                FIXTURE_BLOCKED_WARNINGS.append("fixture_contest_blocked_from_non_test_run")
            continue
            
        if not os.path.exists(source_file):
            continue
            
        try:
            import contest_manager
            sh_name = contest.get("sheet_name", None)
            res = contest_manager.inspect_and_load_file(source_file, sheet_name=sh_name)
            if res["status"] != "success":
                continue
            df_c = res["df"]
        except Exception:
            continue
            
        # Clean columns
        df_c.columns = [str(c).strip() for c in df_c.columns]
        
        # Standardize precinct column in contest file
        df_c["PREC_NORM"] = df_c[precinct_column].apply(
            lambda x: str(x).strip().zfill(7) if str(x).strip().isdigit() else str(x).strip().upper()
        )
        
        # Get classifications for this contest
        c_class = column_classification_matrix[column_classification_matrix["contest_id"] == contest_id]
        
        # Extract mappings
        support_cols = []
        opposition_cols = []
        turnout_cols = []
        persuasion_cols = []
        issue_cols = []
        partisan_cols = []
        denominator_cols = []
        registered_voters_cols = []
        
        # Map original columns and their properties
        col_properties = {}
        for _, row in c_class.iterrows():
            orig_col = row["original_column_name"]
            if orig_col not in df_c.columns:
                continue
            col_properties[orig_col] = row
            
            sig_type = str(row.get("mapped_signal_type", "")).strip().lower()
            rel = str(row.get("current_campaign_relationship", "")).strip().lower()
            
            if sig_type == "ignore" or rel == "ignore":
                continue
                
            if sig_type == "support" or rel == "supports_current_campaign":
                support_cols.append(orig_col)
            elif sig_type == "opposition" or rel == "opposes_current_campaign":
                opposition_cols.append(orig_col)
            elif sig_type == "turnout" or rel == "turnout_only":
                turnout_cols.append(orig_col)
            elif sig_type == "persuasion" or str(row.get("directionality")).strip() == "higher_indicates_persuasion_opportunity":
                persuasion_cols.append(orig_col)
            elif sig_type == "issue_alignment" or rel == "issue_similarity":
                issue_cols.append(orig_col)
            elif sig_type == "partisan_baseline":
                partisan_cols.append(orig_col)
            
            # Check denominators
            denom_col = row.get("denominator_column")
            if pd.notna(denom_col) and str(denom_col).strip() in df_c.columns:
                denominator_cols.append(str(denom_col).strip())
                
            if sig_type == "total_votes" or sig_type == "denominator":
                denominator_cols.append(orig_col)
            elif sig_type == "registered_voters":
                registered_voters_cols.append(orig_col)
        
        # Grouped sum calculations per PREC_NORM
        grouped_data = {}
        for prec_norm, sub_df in df_c.groupby("PREC_NORM"):
            def weighted_sum(cols):
                active_cols = []
                for c in cols:
                    if c in col_properties:
                        inc = col_properties[c].get("include_in_scoring", True)
                        if str(inc).strip().lower() in ["false", "0", "none"]:
                            continue
                    active_cols.append(c)
                    
                if not active_cols:
                    return np.nan
                
                col_sums = []
                for c in active_cols:
                    weight = 1.0
                    if c in col_properties:
                        weight = float(col_properties[c].get("signal_weight", 1.0))
                    
                    vals = pd.to_numeric(sub_df[c], errors='coerce').dropna()
                    if not vals.empty:
                        col_sums.append(vals.sum() * weight)
                
                if not col_sums:
                    return np.nan
                return sum(col_sums)

            # Check for specific denominator columns configured
            support_denom_cols = []
            for c in support_cols:
                if c in col_properties:
                    d_col = col_properties[c].get("denominator_column")
                    if pd.notna(d_col) and str(d_col).strip() in sub_df.columns:
                        support_denom_cols.append(str(d_col).strip())

            opp_denom_cols = []
            for c in opposition_cols:
                if c in col_properties:
                    d_col = col_properties[c].get("denominator_column")
                    if pd.notna(d_col) and str(d_col).strip() in sub_df.columns:
                        opp_denom_cols.append(str(d_col).strip())

            support_votes = weighted_sum(support_cols)
            opposition_votes = weighted_sum(opposition_cols)
            turnout_votes = weighted_sum(turnout_cols)
            persuasion_votes = weighted_sum(persuasion_cols)
            issue_votes = weighted_sum(issue_cols)
            partisan_votes = weighted_sum(partisan_cols)
            registered_voters = weighted_sum(registered_voters_cols)
            
            # Fallback registered voters
            if pd.isna(registered_voters):
                all_configured_denoms = list(set(support_denom_cols + opp_denom_cols))
                if all_configured_denoms:
                    registered_voters = weighted_sum(all_configured_denoms)
            
            total_relevant_votes = weighted_sum(list(set(denominator_cols)))
            if pd.isna(total_relevant_votes):
                all_configured_denoms = list(set(support_denom_cols + opp_denom_cols))
                if all_configured_denoms:
                    total_relevant_votes = weighted_sum(all_configured_denoms)
            if pd.isna(total_relevant_votes) and (pd.notna(support_votes) or pd.notna(opposition_votes)):
                total_relevant_votes = (support_votes or 0.0) + (opposition_votes or 0.0)
                if total_relevant_votes <= 0.0:
                    total_relevant_votes = np.nan

            measure_total_votes = weighted_sum(list(set(denominator_cols)))
            if pd.isna(measure_total_votes):
                measure_total_votes = total_relevant_votes

            grouped_data[prec_norm] = {
                "support_votes": support_votes,
                "opposition_votes": opposition_votes,
                "turnout_votes": turnout_votes,
                "persuasion_votes": persuasion_votes,
                "issue_votes": issue_votes,
                "partisan_votes": partisan_votes,
                "registered_voters": registered_voters,
                "total_relevant_votes": total_relevant_votes,
                "measure_total_votes": measure_total_votes
            }

        # Match each voter precinct from production_df
        for p in precincts:
            p_clean = str(p).strip()
            if p_clean.endswith(".0"):
                p_clean = p_clean[:-2]
            p_upper = p_clean.upper()
            
            # Resolve join
            matched_row = None
            match_status = "unmatched"
            is_inherited = False
            parent_sov = "None"
            
            if uses_crosswalk and p_upper in contest_cross_map:
                xref = contest_cross_map[p_upper]
                if str(xref.get("Valid_For_Production", "")).upper() == "TRUE":
                    voting_p = str(xref.get("Voting_Precinct", "")).strip()
                    if voting_p.endswith(".0"):
                        voting_p = voting_p[:-2]
                    if voting_p.isdigit():
                        voting_p = voting_p.zfill(7)
                    voting_p_upper = voting_p.upper()
                    
                    if voting_p_upper in grouped_data:
                        matched_row = grouped_data[voting_p_upper]
                        parent_sov = voting_p
                        rule = str(xref.get("Match_Rule", ""))
                        if rule == "exact_match":
                            match_status = "exact"
                            is_inherited = False
                        else:
                            match_status = "inherited"
                            is_inherited = True
            
            # Fall back to exact padded match if unmatched
            if matched_row is None:
                p_padded = p_clean.zfill(7).upper()
                if p_padded in grouped_data:
                    matched_row = grouped_data[p_padded]
                    match_status = "exact"
                    is_inherited = False
                    parent_sov = p_padded
                elif p_upper in grouped_data:
                    matched_row = grouped_data[p_upper]
                    match_status = "exact"
                    is_inherited = False
                    parent_sov = p_upper

            # Default values if unmatched
            if matched_row is None:
                matched_row = {
                    "support_votes": np.nan,
                    "opposition_votes": np.nan,
                    "turnout_votes": np.nan,
                    "persuasion_votes": np.nan,
                    "issue_votes": np.nan,
                    "partisan_votes": np.nan,
                    "registered_voters": np.nan,
                    "total_relevant_votes": np.nan,
                    "measure_total_votes": np.nan
                }
                match_status = "unmatched"
                is_inherited = False
                parent_sov = "None"

            # Warnings accumulation
            warnings = []
            if match_status == "unmatched":
                warnings.append("unmatched_precinct")
            if is_inherited:
                warnings.append("inherited_crosswalk")
                
            # Denominator checks
            p_support = matched_row.get("support_votes")
            p_opp = matched_row.get("opposition_votes")
            p_reg = matched_row.get("registered_voters")
            p_turnout_v = matched_row.get("turnout_votes")
            p_total_rel = matched_row.get("total_relevant_votes")
            p_measure_total = matched_row.get("measure_total_votes")

            vote_share_denom = (p_support or 0.0) + (p_opp or 0.0)
            if pd.isna(p_support) and pd.isna(p_opp):
                vote_share_denom = np.nan

            # support_vote_share / opposition_vote_share / margin_vote_share
            if pd.isna(vote_share_denom) or vote_share_denom <= 0:
                warnings.append("missing_vote_share_denominator")
                support_vote_share = np.nan
                opposition_vote_share = np.nan
            else:
                support_vote_share = p_support / vote_share_denom if pd.notna(p_support) else np.nan
                opposition_vote_share = p_opp / vote_share_denom if pd.notna(p_opp) else np.nan
            margin_vote_share = support_vote_share - opposition_vote_share if pd.notna(support_vote_share) and pd.notna(opposition_vote_share) else np.nan

            # support_registered_rate / opposition_registered_rate / margin_registered_rate / turnout_rate
            if pd.isna(p_reg) or p_reg <= 0:
                warnings.append("missing_registered_voters_denominator")
                support_registered_rate = np.nan
                opposition_registered_rate = np.nan
                turnout_rate = np.nan
            else:
                support_registered_rate = p_support / p_reg if pd.notna(p_support) else np.nan
                opposition_registered_rate = p_opp / p_reg if pd.notna(p_opp) else np.nan
                turnout_rate = p_turnout_v / p_reg if pd.notna(p_turnout_v) else np.nan
            margin_registered_rate = support_registered_rate - opposition_registered_rate if pd.notna(support_registered_rate) and pd.notna(opposition_registered_rate) else np.nan

            # issue_support_rate / issue_opposition_rate
            if pd.isna(p_measure_total) or p_measure_total <= 0:
                warnings.append("missing_measure_total_votes_denominator")
                issue_support_rate = np.nan
                issue_opposition_rate = np.nan
            else:
                issue_support_rate = p_support / p_measure_total if pd.notna(p_support) else np.nan
                issue_opposition_rate = p_opp / p_measure_total if pd.notna(p_opp) else np.nan

            # Impossible rates validation check
            active_cols = [c for c in col_properties if col_properties[c].get("include_in_scoring", True)]
            is_odds_ratio = False
            for c in active_cols:
                if "odds_ratio" in c.lower() or "odds ratio" in c.lower():
                    is_odds_ratio = True
            
            if not is_odds_ratio:
                for rate_val in [support_vote_share, opposition_vote_share, support_registered_rate, opposition_registered_rate, turnout_rate, issue_support_rate, issue_opposition_rate]:
                    if pd.notna(rate_val) and rate_val > 1.0:
                        if "impossible_rate_detected" not in warnings:
                            warnings.append("impossible_rate_detected")

            # Other signals
            pers_v = matched_row.get("persuasion_votes")
            p_pers_rate = pers_v / p_total_rel if pd.notna(pers_v) and pd.notna(p_total_rel) and p_total_rel > 0 else np.nan
            
            issue_v = matched_row.get("issue_votes")
            p_issue_rate = issue_v / p_measure_total if pd.notna(issue_v) and pd.notna(p_measure_total) and p_measure_total > 0 else np.nan
            
            part_v = matched_row.get("partisan_votes")
            p_part_rate = part_v / p_total_rel if pd.notna(part_v) and pd.notna(p_total_rel) and p_total_rel > 0 else np.nan

            # Determine outputs based on inheritance rules
            if is_inherited:
                out_support_votes = np.nan
                out_opp_votes = np.nan
                out_turnout_votes = np.nan
                out_total_rel_votes = np.nan
                out_reg_voters = np.nan
            else:
                out_support_votes = matched_row.get("support_votes")
                out_opp_votes = matched_row.get("opposition_votes")
                out_turnout_votes = matched_row.get("turnout_votes")
                out_total_rel_votes = matched_row.get("total_relevant_votes")
                out_reg_voters = matched_row.get("registered_voters")
                
            # Legacy rates mapping safely by contest type
            c_type = str(contest_type).strip().lower()
            has_registered_denom = False
            for c in support_cols:
                if c in col_properties and col_properties[c].get("denominator_type") == "registered_voters":
                    has_registered_denom = True
                    
            if "turnout" in c_type:
                support_rate = np.nan
                opposition_rate = np.nan
                margin_rate = np.nan
            elif has_registered_denom or any(x in c_type for x in ["partisan", "baseline", "support density", "registered"]):
                support_rate = support_registered_rate
                opposition_rate = opposition_registered_rate
                margin_rate = margin_registered_rate
            elif any(x in c_type for x in ["measure", "prop", "proposition", "initiative"]):
                support_rate = issue_support_rate
                opposition_rate = issue_opposition_rate
                margin_rate = issue_support_rate - issue_opposition_rate
            else:
                support_rate = support_vote_share
                opposition_rate = opposition_vote_share
                margin_rate = margin_vote_share
            
            persuasion_signal = p_pers_rate
            turnout_signal = turnout_rate
            issue_alignment_signal = p_issue_rate
            partisan_baseline_signal = p_part_rate
            
            # Goal-based score assignment
            goal = str(current_campaign_profile.get("primary_campaign_goal", "")).strip().lower()
            if "elect" in goal or "pass" in goal:
                contest_signal_score = support_rate
            elif "defeat" in goal:
                contest_signal_score = opposition_rate
            elif "turnout" in goal:
                contest_signal_score = turnout_rate
            elif "persuasion" in goal:
                contest_signal_score = persuasion_signal if pd.notna(persuasion_signal) else (1.0 - abs(margin_rate) if pd.notna(margin_rate) else np.nan)
            else:
                contest_signal_score = support_rate
                
            # Column-level weights & confidence multiplier
            if active_cols:
                avg_col_conf = np.mean([float(col_properties[c].get("confidence_weight", 1.0)) for c in active_cols])
            else:
                avg_col_conf = 1.0

            # Match status confidence calculation
            if match_status == "exact":
                status_mult = 1.0
            elif match_status == "inherited":
                status_mult = 0.9
            else:
                status_mult = 0.0
            
            contest_signal_confidence = confidence_weight * status_mult
            effective_signal_confidence = contest_signal_confidence * avg_col_conf

            # Calculate signal weights used
            def get_group_weight(cols):
                w_list = []
                for c in cols:
                    if c in col_properties and str(col_properties[c].get("include_in_scoring", True)).strip().lower() not in ["false", "0", "none"]:
                        w_list.append(float(col_properties[c].get("signal_weight", 1.0)))
                return sum(w_list) if w_list else 0.0

            support_signal_weight_used = get_group_weight(support_cols)
            opposition_signal_weight_used = get_group_weight(opposition_cols)
            turnout_signal_weight_used = get_group_weight(turnout_cols)
            issue_signal_weight_used = get_group_weight(issue_cols)
            effective_contest_weight = contest_weight
            
            records.append({
                "PrecinctName": p,
                "contest_id": contest_id,
                "contest_name": contest_name,
                "contest_type": contest_type,
                "scope_status": contest.get("scope_status", "valid"),
                "match_status": match_status,
                "contest_weight": contest_weight,
                "confidence_weight": confidence_weight,
                "support_votes": out_support_votes,
                "opposition_votes": out_opp_votes,
                "total_relevant_votes": out_total_rel_votes,
                "turnout_votes": out_turnout_votes,
                "registered_voters": out_reg_voters,
                "support_rate": support_rate,
                "opposition_rate": opposition_rate,
                "margin_rate": margin_rate,
                "turnout_rate": turnout_rate,
                "persuasion_signal": persuasion_signal,
                "turnout_signal": turnout_signal,
                "issue_alignment_signal": issue_alignment_signal,
                "partisan_baseline_signal": partisan_baseline_signal,
                "contest_signal_score": contest_signal_score,
                "contest_signal_confidence": contest_signal_confidence,
                "contest_signal_source": os.path.basename(source_file),
                "contest_result_is_inherited": is_inherited,
                "parent_sov_precinct": parent_sov,
                "raw_parent_votes_duplicated": False,
                "warning_flags": "; ".join(warnings) if warnings else "PASS",
                "support_vote_share": support_vote_share,
                "opposition_vote_share": opposition_vote_share,
                "support_registered_rate": support_registered_rate,
                "opposition_registered_rate": opposition_registered_rate,
                "issue_support_rate": issue_support_rate,
                "issue_opposition_rate": issue_opposition_rate,
                "margin_vote_share": margin_vote_share,
                "margin_registered_rate": margin_registered_rate,
                "support_signal_weight_used": support_signal_weight_used,
                "opposition_signal_weight_used": opposition_signal_weight_used,
                "turnout_signal_weight_used": turnout_signal_weight_used,
                "issue_signal_weight_used": issue_signal_weight_used,
                "effective_contest_weight": effective_contest_weight,
                "effective_signal_confidence": effective_signal_confidence
            })
            
    return pd.DataFrame(records)

def aggregate_precinct_signal_scores(
    precinct_contest_signal_matrix,
    contest_library
):
    """
    Aggregates contest-level precinct signals into weighted campaign readiness scores.
    One row per precinct.
    """
    # Build list of enabled contest ids
    enabled_contests = {c["contest_id"] for c in contest_library if c.get("enabled", True)}
    
    df_mat = precinct_contest_signal_matrix.copy()
    
    # Update weights dynamically from contest_library parameters to prevent stale values
    for c in contest_library:
        c_id = c.get("contest_id")
        if c_id:
            df_mat.loc[df_mat["contest_id"] == c_id, "effective_contest_weight"] = float(c.get("contest_weight", 1.0))
            df_mat.loc[df_mat["contest_id"] == c_id, "effective_signal_confidence"] = float(c.get("confidence_weight", 1.0))
            
    # Filter for enabled contests
    df_mat = df_mat[df_mat["contest_id"].isin(enabled_contests)]
    
    precincts = df_mat["PrecinctName"].unique()
    agg_records = []
    
    for p in precincts:
        sub = df_mat[df_mat["PrecinctName"] == p]
        
        def weighted_avg(val_col):
            # Compute total product weight: effective_contest_weight * effective_signal_confidence
            vals = sub[val_col]
            weights = sub["effective_contest_weight"] * sub["effective_signal_confidence"]
            
            mask = vals.notna() & weights.notna() & (weights > 0)
            if not mask.any():
                return np.nan
                
            w_sum = weights[mask].sum()
            return (vals[mask] * weights[mask]).sum() / w_sum if w_sum > 0 else np.nan

        support_score = weighted_avg("support_rate")
        opposition_score = weighted_avg("opposition_rate")
        margin_score = support_score - opposition_score if pd.notna(support_score) and pd.notna(opposition_score) else np.nan
        persuasion_score = weighted_avg("persuasion_signal")
        turnout_score = weighted_avg("turnout_rate")
        issue_score = weighted_avg("issue_alignment_signal")
        partisan_score = weighted_avg("partisan_baseline_signal")
        
        # Confidence is the maximum or weighted average confidence across enabled
        confidence = sub["effective_signal_confidence"].mean() if len(sub) > 0 else np.nan
        
        exact_c = (sub["match_status"] == "exact").sum()
        inherited_c = (sub["match_status"] == "inherited").sum()
        unmatched_c = (sub["match_status"] == "unmatched").sum()
        
        enabled_c = len(sub)
        
        # Warning Flags logic
        warns = []
        if unmatched_c > 0:
            warns.append("has_unmatched_contests")
        if inherited_c > 0:
            warns.append("has_inherited_signals")
        if pd.isna(support_score):
            warns.append("missing_aggregate_support")
            
        agg_records.append({
            "PrecinctName": p,
            "Aggregate_Support_Score": support_score,
            "Aggregate_Opposition_Score": opposition_score,
            "Aggregate_Margin_Score": margin_score,
            "Aggregate_Persuasion_Score": persuasion_score,
            "Aggregate_Turnout_Score": turnout_score,
            "Aggregate_Issue_Alignment_Score": issue_score,
            "Aggregate_Partisan_Baseline_Score": partisan_score,
            "Aggregate_Contest_Confidence": confidence,
            "Enabled_Contest_Count": enabled_c,
            "Support_Contest_Count": sub[sub["support_rate"].notna()]["contest_id"].nunique(),
            "Opposition_Contest_Count": sub[sub["opposition_rate"].notna()]["contest_id"].nunique(),
            "Turnout_Contest_Count": sub[sub["turnout_rate"].notna()]["contest_id"].nunique(),
            "Issue_Contest_Count": sub[sub["issue_alignment_signal"].notna()]["contest_id"].nunique(),
            "Exact_Signal_Count": exact_c,
            "Inherited_Signal_Count": inherited_c,
            "Missing_Signal_Count": unmatched_c,
            "Warning_Flags": "; ".join(warns) if warns else "PASS"
        })
        
    return pd.DataFrame(agg_records)

def generate_preview_rankings(
    production_df,
    aggregate_signal_scores,
    current_campaign_profile
):
    """
    Generates preview scores and ranks comparing the validated baseline production
    rank to the preview multi-contest rankings.
    """
    df_prod = production_df.copy()
    df_agg = aggregate_signal_scores.copy()
    
    # Merge on PrecinctName
    df_merged = df_prod.merge(df_agg, on="PrecinctName", how="left")
    
    # Store validated baseline rank
    df_merged["Baseline_Final_Rank"] = df_merged["Final_Rank"]
    
    # Define goal and calculate coverage, component score and warnings row-wise
    goal = str(current_campaign_profile.get("primary_campaign_goal", "")).strip().lower()
    
    contest_components = []
    coverage_values = []
    warning_flags_list = []
    
    for idx, row in df_merged.iterrows():
        sup = row.get("Aggregate_Support_Score")
        opp = row.get("Aggregate_Opposition_Score")
        margin = row.get("Aggregate_Margin_Score")
        pers = row.get("Aggregate_Persuasion_Score")
        turnout = row.get("Aggregate_Turnout_Score")
        issue = row.get("Aggregate_Issue_Alignment_Score")
        conf = row.get("Aggregate_Contest_Confidence")
        cnt = row.get("Enabled_Contest_Count", 0)
        
        row_warns = []
        if pd.isna(sup):
            row_warns.append("missing_support_signal")
        if pd.isna(opp):
            row_warns.append("missing_opposition_signal")
        if pd.isna(turnout):
            row_warns.append("missing_turnout_signal")
        if pd.isna(issue):
            row_warns.append("missing_issue_signal")
            
        # Determine expected components and weights
        if "elect" in goal or "pass" in goal:
            expected = [("support", sup, 0.5), ("margin", margin, 0.3), ("turnout", turnout, 0.2)]
        elif "defeat" in goal:
            expected = [("opposition", opp, 0.5), ("support_inv", 1.0 - sup if pd.notna(sup) else np.nan, 0.3), ("turnout", turnout, 0.2)]
        elif "turnout" in goal:
            expected = [("turnout", turnout, 0.6), ("support", sup, 0.4)]
        elif "persuasion" in goal:
            expected = [("persuasion", pers, 0.6), ("margin_inv", 1.0 - abs(margin) if pd.notna(margin) else np.nan, 0.4)]
        else:
            expected = [("support", sup, 0.5), ("margin", margin, 0.5)]
            
        valid_expected = [(name, val, w) for name, val, w in expected if pd.notna(val)]
        
        # Calculate coverage
        coverage = len(valid_expected) / len(expected) if expected else 0.0
        coverage_values.append(coverage)
        
        if not valid_expected:
            contest_comp = np.nan
            if "no_enabled_contest_signals" not in row_warns:
                row_warns.append("no_enabled_contest_signals")
        else:
            val_sum = sum(val * w for name, val, w in valid_expected)
            w_sum = sum(w for name, val, w in valid_expected)
            contest_comp = val_sum / w_sum if w_sum > 0 else np.nan
            if coverage < 1.0:
                row_warns.append("preview_score_partial")
                
        if pd.notna(conf) and conf < 0.5:
            row_warns.append("preview_score_low_confidence")
            
        contest_components.append(contest_comp)
        warning_flags_list.append("; ".join(row_warns) if row_warns else "PASS")
        
    df_merged["Preview_Baseline_Component"] = df_merged["Base_Priority_Score"]
    df_merged["Preview_Contest_Component"] = contest_components
    df_merged["Preview_Model_Coverage"] = coverage_values
    df_merged["Preview_Warning_Flags"] = warning_flags_list
    
    # Calculate composite blend
    composites = []
    for idx, row in df_merged.iterrows():
        cov = row["Preview_Model_Coverage"]
        base = row["Preview_Baseline_Component"]
        cnt_comp = row["Preview_Contest_Component"]
        
        if cov > 0:
            comp = (1.0 - cov) * base + cov * cnt_comp
        else:
            comp = base
        composites.append(comp)
        
    df_merged["Preview_MultiContest_Composite_Score"] = composites
    
    df_merged["Preview_MultiContest_Support_Score"] = df_merged["Aggregate_Support_Score"]
    df_merged["Preview_MultiContest_Opposition_Score"] = df_merged["Aggregate_Opposition_Score"]
    df_merged["Preview_MultiContest_Margin_Score"] = df_merged["Aggregate_Margin_Score"]
    df_merged["Preview_MultiContest_Persuasion_Score"] = df_merged["Aggregate_Persuasion_Score"]
    df_merged["Preview_MultiContest_Turnout_Score"] = df_merged["Aggregate_Turnout_Score"]
    df_merged["Preview_MultiContest_Issue_Alignment_Score"] = df_merged["Aggregate_Issue_Alignment_Score"]
    df_merged["Preview_MultiContest_Confidence"] = df_merged["Aggregate_Contest_Confidence"]
    
    # Sort deterministically
    df_final = df_merged.sort_values(
        by=[
            "Preview_MultiContest_Composite_Score",
            "Preview_Model_Coverage",
            "Preview_MultiContest_Confidence",
            "Baseline_Final_Rank",
            "PrecinctName"
        ],
        ascending=[False, False, False, True, True],
        na_position="last"
    )
    
    df_final["Preview_Rank"] = range(1, len(df_final) + 1)
    df_final["Preview_Rank_Change"] = df_final["Baseline_Final_Rank"] - df_final["Preview_Rank"]
    
    # Strategic signals categorization
    buckets = []
    reasons = []
    
    for idx, r in df_final.iterrows():
        sup = r["Preview_MultiContest_Support_Score"]
        op = r["Preview_MultiContest_Opposition_Score"]
        trn = r["Preview_MultiContest_Turnout_Score"]
        conf = r["Preview_MultiContest_Confidence"]
        cnt = r.get("Enabled_Contest_Count", 0)
        
        sup_ok = pd.notna(sup)
        op_ok = pd.notna(op)
        trn_ok = pd.notna(trn)
        
        if pd.isna(conf) or conf < 0.3 or pd.isna(cnt) or cnt == 0:
            buckets.append("Low information / needs review")
            reasons.append("Low contest confidence weight or zero active contests")
        elif sup_ok and sup >= 0.6 and trn_ok and trn >= 0.6:
            buckets.append("Strong support / high turnout")
            reasons.append("Support rate >= 60% and Turnout rate >= 60%")
        elif sup_ok and sup >= 0.6 and trn_ok and trn < 0.4:
            buckets.append("Strong support / low turnout")
            reasons.append("Support rate >= 60% and Turnout rate < 40%")
        elif op_ok and op >= 0.6:
            buckets.append("Opposition stronghold")
            reasons.append("Opposition rate >= 60%")
        elif trn_ok and trn >= 0.6 and sup_ok and sup < 0.4:
            buckets.append("High turnout / low support")
            reasons.append("Turnout rate >= 60% and Support rate < 40%")
        elif sup_ok and sup >= 0.6 and conf < 0.5:
            buckets.append("High support / low confidence")
            reasons.append("Support rate >= 60% but Average match confidence < 50%")
        elif sup_ok and sup >= 0.4 and sup <= 0.6 and trn_ok and trn >= 0.4:
            buckets.append("Persuasion opportunity")
            reasons.append("Support rate between 40% and 60% and Turnout rate >= 40%")
        elif trn_ok and trn < 0.4 and sup_ok and sup >= 0.5:
            buckets.append("High turnout opportunity")
            reasons.append("Turnout rate < 40% and Support rate >= 50%")
        else:
            buckets.append("Mixed signals")
            reasons.append("Does not meet explicit threshold categories")
            
    df_final["Strategic_Bucket"] = buckets
    df_final["Strategic_Bucket_Reason"] = reasons
    
    return df_final[[
        "PrecinctName", "Preview_MultiContest_Support_Score", "Preview_MultiContest_Opposition_Score",
        "Preview_MultiContest_Margin_Score", "Preview_MultiContest_Persuasion_Score",
        "Preview_MultiContest_Turnout_Score", "Preview_MultiContest_Issue_Alignment_Score",
        "Preview_MultiContest_Confidence", "Preview_MultiContest_Composite_Score", "Preview_Rank",
        "Baseline_Final_Rank", "Preview_Rank_Change", "Strategic_Bucket", "Strategic_Bucket_Reason",
        "Preview_Baseline_Component", "Preview_Contest_Component", "Preview_Model_Coverage", "Preview_Warning_Flags"
    ]]

def generate_correlation_matrix(precinct_contest_signal_matrix):
    """
    Computes a Pearson correlation matrix between contest rates across precincts.
    """
    df = precinct_contest_signal_matrix.copy()
    if df.empty:
        return pd.DataFrame()
        
    # Pivot table to get support_rate per contest_id for each PrecinctName
    pivoted_sup = df.pivot_table(index="PrecinctName", columns="contest_name", values="support_rate", aggfunc='mean')
    pivoted_trn = df.pivot_table(index="PrecinctName", columns="contest_name", values="turnout_rate", aggfunc='mean')
    
    # Rename columns to distinguish support vs turnout
    pivoted_sup = pivoted_sup.rename(columns=lambda x: f"{x}_SupportRate")
    pivoted_trn = pivoted_trn.rename(columns=lambda x: f"{x}_TurnoutRate")
    
    combined = pd.concat([pivoted_sup, pivoted_trn], axis=1)
    
    # Calculate correlations
    corr = combined.corr(method="pearson")
    corr.insert(0, "Indicator_Name", corr.index)
    return corr

def generate_contest_signal_validation_report(
    contest_library,
    column_classification_matrix,
    precinct_contest_signal_matrix,
    current_campaign_profile
):
    """
    Generates a diagnostics markdown validation report for the multi-contest profile.
    """
    profile_str = json.dumps(current_campaign_profile, indent=2)
    
    # Calculate library summaries
    lines = []
    lines.append("# Contest Signal Manager Validation Report")
    lines.append(f"\n## Current Campaign Profile\n```json\n{profile_str}\n```\n")
    
    # Enabled/Disabled counts
    total_contests = len(contest_library)
    enabled_count = sum(1 for c in contest_library if c.get("enabled", True))
    disabled_count = total_contests - enabled_count
    lines.append("## General Configuration Stats")
    lines.append(f"- **Total Contests in Library:** {total_contests}")
    lines.append(f"- **Enabled Contests:** {enabled_count}")
    lines.append(f"- **Disabled Contests:** {disabled_count}")
    
    # Ignored columns count
    ignored_col_count = len(column_classification_matrix[
        (column_classification_matrix["user_classification"].str.strip().str.lower() == "ignore") |
        (column_classification_matrix["mapped_signal_type"].str.strip().str.lower() == "ignore")
    ])
    lines.append(f"- **Ignored Columns Count:** {ignored_col_count}")
    
    # Fixture contest detection
    fixture_contests_detected = []
    for c in contest_library:
        if is_fixture_path(c.get("source_file", "")):
            fixture_contests_detected.append(c.get("contest_name", "Unnamed"))
    if fixture_contests_detected:
        lines.append(f"- **Fixture Contests Detected:** {', '.join(fixture_contests_detected)}")
    else:
        lines.append("- **Fixture Contests Detected:** None")
        
    # Check if fixture contests were blocked from non-test run
    if FIXTURE_BLOCKED_WARNINGS:
        lines.append(f"- **Fixture Warnings:** {', '.join(FIXTURE_BLOCKED_WARNINGS)}")
    else:
        lines.append("- **Fixture Warnings:** None")
        
    # Production outputs untouched
    lines.append("- **Production Priority Precincts File Untouched:** Yes (Baseline final ranks remain unchanged by preview modes)")

    lines.append("\n## Registered Contests Summary")
    lines.append("| Contest ID | Contest Name | Type | Weight | Confidence | Enabled | Coverage | Scope |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for c in contest_library:
        cid = c.get("contest_id")
        sub = precinct_contest_signal_matrix[precinct_contest_signal_matrix["contest_id"] == cid]
        cov = "0.00%"
        if not sub.empty:
            matched = (sub["match_status"] != "unmatched").sum()
            total = len(sub)
            cov = f"{(matched / total * 100.0):.2f}%" if total > 0 else "0.00%"
            
        lines.append(
            f"| {cid} | {c.get('contest_name')} | {c.get('contest_type')} | {c.get('contest_weight')} | "
            f"{c.get('confidence_weight')} | {c.get('enabled')} | {cov} | {c.get('scope_status')} |"
        )
        
    # Rates and Denominators Analysis by Contest
    lines.append("\n## Contest Rates & Denominators Diagnostics")
    
    impossible_rate_found = False
    
    for c in contest_library:
        cid = c.get("contest_id")
        cname = c.get("contest_name")
        sub = precinct_contest_signal_matrix[precinct_contest_signal_matrix["contest_id"] == cid]
        
        if sub.empty:
            continue
            
        lines.append(f"### Contest: {cname} (`{cid}`)")
        
        # Denominator analysis
        c_class = column_classification_matrix[column_classification_matrix["contest_id"] == cid]
        denoms_used = []
        for _, row in c_class.iterrows():
            d_type = row.get("denominator_type")
            d_col = row.get("denominator_column")
            if pd.notna(d_type) and d_type:
                denoms_used.append(f"{row['original_column_name']} -> {d_type} (col: {d_col})")
        
        lines.append(f"- **Denominator Configs:** {', '.join(denoms_used) if denoms_used else 'None classified'}")
        
        has_registered_denom = sub["registered_voters"].notna().any()
        has_vote_share_denom = (sub["support_votes"].notna() | sub["opposition_votes"].notna()).any()
        
        lines.append(f"- **Support Vote-Share Denominator Parsed (support_votes + opposition_votes):** {'Yes' if has_vote_share_denom else 'No'}")
        lines.append(f"- **Registered-Voter Denominator Parsed (registered_voters):** {'Yes' if has_registered_denom else 'No'}")
        
        rate_metrics = [
            ("support_rate", "Support Rate"),
            ("opposition_rate", "Opposition Rate"),
            ("turnout_rate", "Turnout Rate"),
            ("support_vote_share", "Support Vote Share"),
            ("opposition_vote_share", "Opposition Vote Share"),
            ("support_registered_rate", "Support Registered Rate"),
            ("opposition_registered_rate", "Opposition Registered Rate"),
            ("issue_support_rate", "Issue Support Rate"),
            ("issue_opposition_rate", "Issue Opposition Rate")
        ]
        
        rate_lines = []
        for field, label in rate_metrics:
            if field in sub.columns:
                vals = sub[field].dropna()
                if not vals.empty:
                    mn = vals.min()
                    mx = vals.max()
                    rate_lines.append(f"  * **{label}:** Min: `{mn:.4f}`, Max: `{mx:.4f}`")
                    
                    is_odds_ratio = False
                    active_cols = c_class[c_class["include_in_scoring"] == True]["original_column_name"].tolist()
                    for col_n in active_cols:
                        if "odds_ratio" in col_n.lower() or "odds ratio" in col_n.lower():
                            is_odds_ratio = True
                    
                    if not is_odds_ratio and mx > 1.0:
                        impossible_rate_found = True
                        rate_lines.append(f"    * ⚠️ **IMPOSSIBLE RATE DETECTED:** Max is `{mx:.4f}` (> 1.0)")
                        
        if rate_lines:
            lines.append("- **Rate Field Diagnostics:**")
            lines.extend(rate_lines)
        else:
            lines.append("- **Rate Field Diagnostics:** No rates computed.")
            
    # Verdict output
    lines.append("\n## Mathematical Soundness Verdict")
    if impossible_rate_found:
        lines.append("> [!CAUTION]")
        lines.append("> **VERDICT: FAIL: impossible_rate_detected**")
        lines.append("> Rates exceeding 1.0 were found on standard (non-odds-ratio) candidate or turnout calculations. Please verify classification denominators.")
    else:
        lines.append("> [!NOTE]")
        lines.append("> **VERDICT: PASS**")
        lines.append("> All computed rates are mathematically within expected 0.0 - 1.0 bounds (or explicitly marked as odds ratios).")

    lines.append("\n## Active Warning Flags")
    warns = precinct_contest_signal_matrix[precinct_contest_signal_matrix["warning_flags"] != "PASS"]
    if warns.empty:
        lines.append("No active warnings detected. All data models comply with validation constraints.")
    else:
        lines.append("| Contest Name | Precinct | Active Warnings |")
        lines.append("| --- | --- | --- |")
        for _, r in warns.head(20).iterrows():
            lines.append(f"| {r['contest_name']} | {r['PrecinctName']} | {r['warning_flags']} |")
        if len(warns) > 20:
            lines.append(f"| ... | and {len(warns) - 20} more warnings | ... |")
            
    lines.append("\n## Disclaimer")
    lines.append("> [!NOTE]")
    lines.append("> All correlation reports, ranking alterations, and diagnostics are reference tools only. ")
    lines.append("> The engine does not make causal predictions or guarantee campaign outcomes from historical context.")
    
    return "\n".join(lines)
