import os
import json
import shutil
from datetime import datetime

DATA_DIR = "data"
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
METADATA_FILE = os.path.join(DATA_DIR, "file_metadata.json")

SYSTEM_ROLES = {
    "Voter File": "voter_file.csv",
    "MPREC Crosswalk": "mprec_srprec.csv",
    "City Map": "srprec_city.csv",
    "District Map": "district_assignment.csv",
    "True Area / Metrics": "srprec_metrics.csv",
    "SRPREC Shapes": "srprec_shapes.zip",
    "City Shapes": "city_shapes.zip",
    "Assembly Shapes": "assembly_shapes.zip",
    "Supervisor Shapes": "supervisorial_shapes.zip",
    "Contest Data": "contest_data_input"  # prefix, extension matches original
}

FILE_TO_ROLE = {v: k for k, v in SYSTEM_ROLES.items() if k != "Contest Data"}

def load_file_metadata(data_dir=DATA_DIR):
    metadata_file = os.path.join(data_dir, "file_metadata.json")
    if not os.path.exists(metadata_file):
        return {}
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_file_metadata(metadata, data_dir=DATA_DIR):
    metadata_file = os.path.join(data_dir, "file_metadata.json")
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return True
    except Exception:
        return False

def delete_system_copy(role, data_dir=DATA_DIR):
    if role == "Contest Data":
        for e in ['.csv', '.tsv', '.xlsx', '.xls']:
            p = os.path.join(data_dir, f"contest_data_input{e}")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
    else:
        dest_filename = SYSTEM_ROLES.get(role)
        if dest_filename:
            p = os.path.join(data_dir, dest_filename)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

def sync_metadata_with_disk(data_dir=DATA_DIR):
    os.makedirs(data_dir, exist_ok=True)
    archive_dir = os.path.join(data_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    metadata = load_file_metadata(data_dir)
    import copy
    old_metadata = copy.deepcopy(metadata)
    
    # 1. Gather all files physically present on disk
    files_in_data = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f)) and f != "file_metadata.json"]
    files_in_archive = [f for f in os.listdir(archive_dir) if os.path.isfile(os.path.join(archive_dir, f))]
    
    # Check what roles are currently assigned to custom user files
    assigned_roles = {}
    for fname, info in list(metadata.items()):
        # If the file is not physically on disk (data or archive), remove from metadata
        on_disk = (info.get("archived") and fname in files_in_archive) or (not info.get("archived") and fname in files_in_data)
        if not on_disk:
            metadata.pop(fname)
            continue
            
        role = info.get("tag")
        if role and role in SYSTEM_ROLES:
            assigned_roles[role] = fname
            
    # 2. Add new files to metadata and auto-detect system names
    all_files = [(f, False) for f in files_in_data] + [(f, True) for f in files_in_archive]
    
    def is_system_filename(f):
        if f in FILE_TO_ROLE:
            return True
        name, ext = os.path.splitext(f)
        if name == "contest_data_input" and ext.lower() in ['.csv', '.tsv', '.xlsx', '.xls']:
            return True
        return False
        
    def get_system_role(f):
        if f in FILE_TO_ROLE:
            return FILE_TO_ROLE[f]
        name, ext = os.path.splitext(f)
        if name == "contest_data_input" and ext.lower() in ['.csv', '.tsv', '.xlsx', '.xls']:
            return "Contest Data"
        return None

    # Step A: Register files that are NOT system names first
    for fname, is_archived in all_files:
        if fname not in metadata:
            if not is_system_filename(fname):
                stat = os.stat(os.path.join(archive_dir if is_archived else data_dir, fname))
                metadata[fname] = {
                    "tag": None,
                    "archived": is_archived,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                }

    # Step B: Register system files.
    # A system file is only shown if NO OTHER user file is currently tagged with its role.
    for fname, is_archived in all_files:
        if is_system_filename(fname):
            role = get_system_role(fname)
            if role:
                other_file_has_role = (role in assigned_roles and assigned_roles[role] != fname)
                if other_file_has_role:
                    if fname in metadata:
                        metadata.pop(fname)
                else:
                    if fname not in metadata:
                        stat = os.stat(os.path.join(archive_dir if is_archived else data_dir, fname))
                        metadata[fname] = {
                            "tag": role,
                            "archived": is_archived,
                            "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        }
                    else:
                        metadata[fname]["tag"] = role

    if metadata != old_metadata:
        print("[DEBUG] sync_metadata_with_disk: Metadata changed. Saving to disk.")
        save_file_metadata(metadata, data_dir)
    else:
        print("[DEBUG] sync_metadata_with_disk: Metadata unchanged. Skipping save.")
    return metadata

def assign_tag_role(filename, role, data_dir=DATA_DIR):
    metadata = load_file_metadata(data_dir)
    if filename not in metadata:
        return False, "File not found in metadata"
        
    if metadata[filename].get("archived"):
        return False, "Cannot tag an archived file. Unarchive it first."
        
    old_role = metadata[filename].get("tag")
    
    if not role or role == "None" or role == "None / Untagged" or role == "None (Untagged)":
        metadata[filename]["tag"] = None
        save_file_metadata(metadata, data_dir)
        if old_role:
            delete_system_copy(old_role, data_dir)
        sync_metadata_with_disk(data_dir)
        return True, f"Successfully untagged {filename}"
        
    if old_role == role:
        return True, "Role is already assigned"
        
    # Untag any other file that currently has this role
    for f, info in metadata.items():
        if info.get("tag") == role and f != filename:
            info["tag"] = None
            
    metadata[filename]["tag"] = role
    save_file_metadata(metadata, data_dir)
    
    src_path = os.path.join(data_dir, filename)
    _, ext = os.path.splitext(filename)
    
    if role == "Contest Data":
        for e in ['.csv', '.tsv', '.xlsx', '.xls']:
            p = os.path.join(data_dir, f"contest_data_input{e}")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
        dest_path = os.path.join(data_dir, f"contest_data_input{ext.lower()}")
    else:
        dest_filename = SYSTEM_ROLES.get(role)
        dest_path = os.path.join(data_dir, dest_filename)
        
    try:
        shutil.copy2(src_path, dest_path)
    except Exception as e:
        return False, f"Failed to copy file to system path: {str(e)}"
        
    if old_role and old_role != role:
        delete_system_copy(old_role, data_dir)
        
    sync_metadata_with_disk(data_dir)
    return True, f"Successfully tagged {filename} as {role}"

def archive_file(filename, data_dir=DATA_DIR):
    metadata = load_file_metadata(data_dir)
    if filename not in metadata:
        return False, "File not found"
        
    if metadata[filename].get("archived"):
        return True, "File is already archived"
        
    role = metadata[filename].get("tag")
    
    src_path = os.path.join(data_dir, filename)
    dest_path = os.path.join(data_dir, "archive", filename)
    
    try:
        shutil.move(src_path, dest_path)
    except Exception as e:
        return False, f"Failed to move file to archive: {str(e)}"
        
    if role:
        metadata[filename]["tag"] = None
        delete_system_copy(role, data_dir)
        
    metadata[filename]["archived"] = True
    save_file_metadata(metadata, data_dir)
    
    sync_metadata_with_disk(data_dir)
    return True, "File archived successfully"

def unarchive_file(filename, data_dir=DATA_DIR):
    metadata = load_file_metadata(data_dir)
    if filename not in metadata:
        return False, "File not found"
        
    if not metadata[filename].get("archived"):
        return True, "File is not archived"
        
    src_path = os.path.join(data_dir, "archive", filename)
    dest_path = os.path.join(data_dir, filename)
    
    try:
        shutil.move(src_path, dest_path)
    except Exception as e:
        return False, f"Failed to move file back from archive: {str(e)}"
        
    metadata[filename]["archived"] = False
    save_file_metadata(metadata, data_dir)
    
    sync_metadata_with_disk(data_dir)
    return True, "File unarchived successfully"

def delete_file(filename, data_dir=DATA_DIR):
    metadata = load_file_metadata(data_dir)
    if filename not in metadata:
        return False, "File not found"
        
    is_archived = metadata[filename].get("archived")
    role = metadata[filename].get("tag")
    
    file_path = os.path.join(data_dir, "archive" if is_archived else "", filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return False, f"Failed to delete file from disk: {str(e)}"
            
    if role:
        delete_system_copy(role, data_dir)
        
    metadata.pop(filename)
    save_file_metadata(metadata, data_dir)
    
    sync_metadata_with_disk(data_dir)
    return True, "File deleted successfully"
