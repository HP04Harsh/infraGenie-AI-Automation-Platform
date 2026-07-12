import sys
with open(sys.argv[1], "rb") as f:
    data = f.read()
print(f"Length: {len(data)}")
print(f"First 200 bytes: {data[:200]}")
print(f"First 200 chars: {data[:200].decode('utf-8', 'replace')}")
