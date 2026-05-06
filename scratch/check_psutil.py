import psutil

def check():
    print("Listing all python processes and their cmdlines:")
    found = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                print(f"PID {proc.info['pid']}: {proc.info['cmdline']}")
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"PID {proc.info['pid']}: ACCESS DENIED")
    
    if not found:
        print("No python processes found.")

if __name__ == "__main__":
    check()
