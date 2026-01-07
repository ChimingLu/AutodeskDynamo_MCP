"""
測試自動化框架 - 自動執行所有測試腳本

此框架會掃描 tests/ 目錄下的所有測試腳本並依序執行，
產生詳細的測試報告，包括成功/失敗統計和執行時間。
"""

import subprocess
import os
import sys
import time
import json
from pathlib import Path

# 測試分類配置
# 結構: { "category_name": { "scripts": [...], "requires_dynamo": bool } }
TEST_CONFIG = {
    "connection": {
        "scripts": ["check_dynamo.py", "check_workspace.py"],
        "requires_dynamo": True
    },
    "node_search": {
        "scripts": ["list_nodes_test.py", "search_aqua.py", "search_clockwork.py", "search_color.py"],
        "requires_dynamo": True
    },
    "node_placement": {
        "scripts": ["place_aqua.py", "draw_line.py", "draw_line_3d.py"],
        "requires_dynamo": True
    },
    "integration": {
        "scripts": ["performance_test.py"],
        "requires_dynamo": True
    },
    "unit_tests": {
        "scripts": ["test_path_info.py"], # 假設這是純單元測試
        "requires_dynamo": False
    }
}

def check_dynamo_process() -> bool:
    """檢查 DynamoSandbox.exe 或 Revit.exe 是否正在執行"""
    try:
        # Check for DynamoSandbox.exe
        output = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq DynamoSandbox.exe" /FO CSV /NH', 
            shell=True
        ).decode('utf-8', errors='ignore')
        
        # Check for Revit.exe
        output_revit = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq Revit.exe" /FO CSV /NH', 
            shell=True
        ).decode('utf-8', errors='ignore')
        
        combined_output = output + "\n" + output_revit
        
        for line in combined_output.splitlines():
            if not line.strip(): continue
            if "DynamoSandbox.exe" in line or "Revit.exe" in line:
                return True
                
        return False
    except Exception as e:
        print(f"⚠️ 無法檢查 Dynamo 進程: {e}")
        return False

class TestRunner:
    def __init__(self, test_dir="tests"):
        self.test_dir = Path(__file__).parent
        self.results = []
        self.start_time = None
        self.end_time = None
        self.dynamo_running = False

    def check_environment(self):
        """檢查測試環境"""
        print("正在檢查環境...")
        self.dynamo_running = check_dynamo_process()
        if self.dynamo_running:
            print("✅ Dynamo/Revit 正在執行")
        else:
            print("⚠️ Dynamo/Revit 未執行 (部分測試將被跳過)")

    def run_test(self, script_path):
        """執行單個測試腳本"""
        script_name = script_path.name
        print(f"  執行中: {script_name}...", end=" ", flush=True)
        
        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30  # 30秒超時
            )
            elapsed = time.time() - start
            
            success = result.returncode == 0
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} ({elapsed:.2f}s)")
            
            return {
                "script": script_name,
                "status": "PASS" if success else "FAIL",
                "duration": elapsed,
                "stdout": result.stdout[:500] if result.stdout else "",  # 限制輸出長度
                "stderr": result.stderr[:500] if result.stderr else "",
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            print(f"⏱️ TIMEOUT ({elapsed:.2f}s)")
            return {
                "script": script_name,
                "status": "TIMEOUT",
                "duration": elapsed,
                "error": "測試執行超時 (30秒)"
            }
        except Exception as e:
            elapsed = time.time() - start
            print(f"💥 ERROR ({elapsed:.2f}s)")
            return {
                "script": script_name,
                "status": "ERROR",
                "duration": elapsed,
                "error": str(e)
            }

    def run_category(self, category_name, config):
        """執行特定類別的測試"""
        print(f"\n[{category_name.upper()}]")
        
        # 檢查是否需要跳過
        if config["requires_dynamo"] and not self.dynamo_running:
            print(f"  ⚠️ 跳過此類別 (需要 Dynamo 執行)")
            skipped_results = []
            for script_name in config["scripts"]:
                skipped_results.append({
                    "script": script_name,
                    "status": "SKIP",
                    "duration": 0,
                    "error": "Dynamo 未執行"
                })
            return skipped_results

        category_results = []
        for script_name in config["scripts"]:
            script_path = self.test_dir / script_name
            if script_path.exists():
                result = self.run_test(script_path)
                category_results.append(result)
            else:
                print(f"  ⚠️ 跳過: {script_name} (檔案不存在)")
                category_results.append({
                    "script": script_name,
                    "status": "SKIP",
                    "duration": 0,
                    "error": "檔案不存在"
                })
        
        return category_results

    def generate_report(self):
        """產生測試報告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        timeout = sum(1 for r in self.results if r["status"] == "TIMEOUT")
        error = sum(1 for r in self.results if r["status"] == "ERROR")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        
        total_time = self.end_time - self.start_time
        
        print("\n" + "=" * 60)
        print(" 測試報告")
        print("=" * 60)
        print(f"總執行時間: {total_time:.2f}秒")
        print(f"總測試數量: {total}")
        print(f"  ✅ 通過: {passed}")
        print(f"  ❌ 失敗: {failed}")
        print(f"  ⚠️ 跳過: {skipped}")
        print(f"  ⏱️ 超時: {timeout}")
        print(f"  💥 錯誤: {error}")
        
        effective_total = total - skipped
        if effective_total > 0:
            print(f"\n執行成功率: {(passed/effective_total*100):.1f}% (排除跳過項目)")
        else:
            print("\n沒有實際執行的測試")
            
        print("=" * 60)
        
        # 失敗測試詳細資訊
        failures = [r for r in self.results if r["status"] in ["FAIL", "TIMEOUT", "ERROR"]]
        if failures:
            print("\n失敗測試詳情:")
            for f in failures:
                print(f"\n  [{f['status']}] {f['script']}")
                if "error" in f:
                    print(f"    錯誤: {f['error']}")
                if f.get("stderr"):
                    print(f"    輸出: {f['stderr'][:200]}")
        
        # 儲存 JSON 報告
        report_path = self.test_dir / "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "timeout": timeout,
                    "error": error,
                    "duration_seconds": total_time,
                    "environment": {
                        "dynamo_running": self.dynamo_running
                    }
                },
                "results": self.results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 詳細報告已儲存至: {report_path}")

    def run_all(self, category_filter=None):
        """執行所有測試或指定類別的測試"""
        print("=" * 60)
        print(" AutodeskDynamo_MCP 測試套件")
        print("=" * 60)
        
        self.start_time = time.time()
        self.check_environment()
        
        if category_filter:
            if category_filter in TEST_CONFIG:
                results = self.run_category(category_filter, TEST_CONFIG[category_filter])
                self.results.extend(results)
            else:
                print(f"❌ 未知的測試類別: {category_filter}")
                print(f"可用類別: {', '.join(TEST_CONFIG.keys())}")
                return
        else:
            # 執行所有類別
            for category_name, config in TEST_CONFIG.items():
                results = self.run_category(category_name, config)
                self.results.extend(results)
        
        self.end_time = time.time()
        self.generate_report()

def main():
    """主函式"""
    if len(sys.argv) > 1:
        # 指定類別執行
        category = sys.argv[1]
        runner = TestRunner()
        runner.run_all(category_filter=category)
    else:
        # 執行所有測試
        runner = TestRunner()
        runner.run_all()

if __name__ == "__main__":
    main()
