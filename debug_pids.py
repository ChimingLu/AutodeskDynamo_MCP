
import subprocess

def _get_system_dynamo_processes() -> list[int]:
    """Get list of PIDs for DynamoSandbox.exe and Revit.exe"""
    pids = []
    try:
        cmd = 'tasklist /FI "IMAGENAME eq DynamoSandbox.exe" /FI "IMAGENAME eq Revit.exe" /FO CSV /NH'
        print(f"Executing: {cmd}")
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        print(f"Output:\n{output}")
        for line in output.splitlines():
            if not line.strip(): continue
            parts = line.split(',')
            if len(parts) < 2: continue
            
            image_name = parts[0].strip('"')
            pid_str = parts[1].strip('"')
            
            if image_name.lower() in ["dynamosandbox.exe", "revit.exe"]:
                if pid_str.isdigit():
                    pids.append(int(pid_str))
    except Exception as e:
        print(f"Error: {e}")
        pass
    return pids

if __name__ == "__main__":
    pids = _get_system_dynamo_processes()
    print(f"System PIDs: {pids}")
