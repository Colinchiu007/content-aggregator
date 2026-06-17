"""
运行所有单元测试

用法:
    python run_tests.py              # 运行所有测试
    python run_tests.py -v         # 详细输出
    python run_tests.py -x         # 遇到第一个失败就停止
    python run_tests.py test_models.py  # 运行指定测试文件
"""

import sys
import os
import argparse
import subprocess


def run_tests(verbose=False, stop_on_first_failure=False, test_files=None, with_coverage=False):
    """
    运行单元测试
    
    Args:
        verbose: 详细输出
        stop_on_first_failure: 遇到第一个失败就停止
        test_files: 指定测试文件列表（None 表示全部）
        with_coverage: 启用覆盖率统计
    """
    # 构建 pytest 命令
    cmd = [sys.executable, "-m", "pytest"]
    
    # 添加选项
    if verbose:
        cmd.append("-v")
    
    if stop_on_first_failure:
        cmd.append("-x")
    
    if with_coverage:
        cmd.extend(["--cov=src/content_aggregator", "--cov-report=term-missing"])
    
    # 添加测试文件
    if test_files:
        for f in test_files:
            cmd.append(os.path.join("tests", f))
    else:
        cmd.append("tests/")
    
    # 打印命令
    print(f"\n{'=' * 60}")
    print(f"运行命令: {' '.join(cmd)}")
    print(f"{'=' * 60}\n")
    
    # 运行测试
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="运行 content-aggregator 单元测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("-x", "--stop-on-first-failure", action="store_true", help="遇到第一个失败就停止")
    parser.add_argument("-c", "--with-coverage", action="store_true", help="启用覆盖率统计")
    parser.add_argument("test_files", nargs="*", help="指定测试文件（如 test_models.py）")
    
    args = parser.parse_args()
    
    # 转换测试文件名
    test_files = args.test_files if args.test_files else None
    
    # 运行测试
    exit_code = run_tests(
        verbose=args.verbose,
        stop_on_first_failure=args.stop_on_first_failure,
        test_files=test_files,
        with_coverage=args.with_coverage
    )
    
    # 返回退出码
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
