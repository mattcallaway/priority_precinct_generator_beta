import pypdf

def dump_pages(path, n_pages=2):
    reader = pypdf.PdfReader(path)
    print("="*80)
    print(f"FILE: {path}")
    print("="*80)
    for i in range(min(n_pages, len(reader.pages))):
        print(f"--- PAGE {i+1} ---")
        text = reader.pages[i].extract_text()
        for idx, line in enumerate(text.split("\n")):
            if idx < 40:
                print(f"{idx}: {repr(line)}")

dump_pages(r"D:\Downloads\ewmr010_regabsvotpctxref_2026-06-02.pdf", 1)
dump_pages(r"D:\Downloads\ewmr008_votabsregpctxref_2026-06-02.pdf", 1)
