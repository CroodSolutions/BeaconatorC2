# Logging function for beacon operations

def beacon_log(message, prefix="BEACON"):
    """Simple logging function with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{prefix}] {message}")
