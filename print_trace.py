with open("test_logs.txt", "rb") as f:
    text = f.read().decode('utf-16', errors='replace')
    with open("trace.txt", "w", encoding='ascii', errors='replace') as o:
        o.write(text)
