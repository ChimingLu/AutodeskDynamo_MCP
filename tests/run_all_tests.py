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

# 測試分類
TEST_CATEGORIES = {
    "connection": ["check_dynamo.py", "check_workspace.py"],
    "node_search": ["list_nodes_test.py", "search_aqua.py", "search_clockwork.py", "search_color.py"],
    "node_placement": ["place_aqua.py", "draw_line.py", "draw_line_3d.py"],
    "integration": ["performance_test.py"],
}

class TestRunner:
    def __init__(self, test_dir="tests"):
        self.test_dir = Path(__file__).parent
        self.results = []
        self.start_time = None
        self.end_time = None

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

    def run_category(self, category, scripts):
        """執行特定類別的測試"""
        print(f"\n[{category.upper()}]")
        category_results = []
        
        for script_name in scripts:
            script_path = self.test_dir / script_name
            if script_path.exists():
                result = self.run_test(script_path)
                category_results.append(result)
            else:
                print(f"  ⚠️ 跳過: {script_name} (檔案不存在)")
        
        return category_results

    def generate_report(self):
        """產生測試報告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        timeout = sum(1 for r in self.results if r["status"] == "TIMEOUT")
        error = sum(1 for r in self.results if r["status"] == "ERROR")
        
        total_time = self.end_time - self.start_time
        
        print("\n" + "=" * 60)
        print(" 測試報告")
        print("=" * 60)
        print(f"總執行時間: {total_time:.2f}秒")
        print(f"總測試數量: {total}")
        print(f"  ✅ 通過: {passed}")
        print(f"  ❌ 失敗: {failed}")
        print(f"  ⏱️ 超時: {timeout}")
        print(f"  💥 錯誤: {error}")
        print(f"\n成功率: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        print("=" * 60)
        
        # 失敗測試詳細資訊
        failures = [r for r in self.results if r["status"] != "PASS"]
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
                    "timeout": timeout,
                    "error": error,
                    "duration_seconds": total_time
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
        
        if category_filter:
            if category_filter in TEST_CATEGORIES:
                results = self.run_category(category_filter, TEST_CATEGORIES[category_filter])
                self.results.extend(results)
            else:
                print(f"❌ 未知的測試類別: {category_filter}")
                print(f"可用類別: {', '.join(TEST_CATEGORIES.keys())}")
                return
        else:
            # 執行所有類別
            for category, scripts in TEST_CATEGORIES.items():
                results = self.run_category(category, scripts)
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
