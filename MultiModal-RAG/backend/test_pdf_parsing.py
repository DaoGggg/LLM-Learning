"""
测试 PDF 解析功能
直接运行此脚本测试解析，无需启动 Flask 服务
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from app.services.pdf_service import pdf_service


def test_pdf_parsing():
    """测试 PDF 解析"""

    # 查找测试 PDF 文件
    test_dir = project_root / "uploads" / "temp"
    pdf_files = list(test_dir.glob("*.pdf"))

    if not pdf_files:
        print("[ERROR] 未找到测试 PDF 文件")
        print(f"请将 PDF 文件上传到: {test_dir}")
        return

    # 选择最大的 PDF 文件进行测试
    pdf_file = max(pdf_files, key=lambda f: f.stat().st_size)
    print(f"[TEST] 使用测试文件: {pdf_file.name}")

    # 1. 获取 PDF 信息
    print("\n[TEST 1] 获取 PDF 信息...")
    try:
        info = pdf_service.get_pdf_info(str(pdf_file))
        print(f"  - 页数: {info['num_pages']}")
        print(f"  - 大小: {info['file_size'] / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"  [ERROR] {e}")
        return

    # 2. 解析第一页
    print("\n[TEST 2] 解析第一页...")
    try:
        result = pdf_service.parse_pdf_by_page(str(pdf_file), page=1)
        print(f"  - 解析到 {len(result['elements'])} 个元素")
        print(f"  - 图片路径: {result['image_path']}")

        # 显示元素列表
        print("\n  元素列表:")
        for elem in result['elements'][:5]:  # 只显示前5个
            coords_info = "有坐标" if elem.get('coordinates') else "无坐标"
            content_preview = elem['content'][:50].replace('\n', ' ') + "..." if len(elem['content']) > 50 else elem['content']
            print(f"    - [{elem['type']}] {coords_info}: {content_preview}")

        if len(result['elements']) > 5:
            print(f"    ... 还有 {len(result['elements']) - 5} 个元素")

        # 3. 测试转换图片
        print("\n[TEST 3] 验证页面图片...")
        if result['image_path']:
            img_path = project_root / "static" / "images" / Path(result['image_path']).name
            if img_path.exists():
                print(f"  - 图片已生成: {img_path.name}")
                print(f"  - 图片大小: {img_path.stat().st_size / 1024:.2f} KB")
            else:
                print(f"  [WARNING] 图片文件不存在: {img_path}")
        else:
            print("  [WARNING] 未生成图片")

        print("\n[SUCCESS] PDF 解析测试完成!")

    except Exception as e:
        print(f"  [ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 50)
    print("PDF 解析功能测试")
    print("=" * 50)
    test_pdf_parsing()
