import requests
import json
import sys

BASE_URL = "http://localhost:8001/api"
USERNAME = "testuser_" + str(hash("test"))[-4:]
PASSWORD = "testpass123"

def test_api():
    print("=== AI模拟平台API测试 ===")
    
    # 1. 注册用户
    print(f"1. 注册用户: {USERNAME}")
    try:
        reg_data = {"username": USERNAME, "password": PASSWORD}
        reg_response = requests.post(f"{BASE_URL}/register", json=reg_data, timeout=10)
        print(f"   状态码: {reg_response.status_code}")
        if reg_response.status_code == 200:
            print(f"   响应: {reg_response.json()}")
        else:
            print(f"   错误: {reg_response.text}")
    except Exception as e:
        print(f"   注册失败: {e}")
        return False
    
    # 2. 登录获取token
    print(f"2. 用户登录")
    try:
        login_data = {"username": USERNAME, "password": PASSWORD}
        login_response = requests.post(f"{BASE_URL}/token", data=login_data, timeout=10)
        print(f"   状态码: {login_response.status_code}")
        if login_response.status_code == 200:
            token_data = login_response.json()
            access_token = token_data.get("access_token")
            print(f"   登录成功，token获取成功")
        else:
            print(f"   登录失败: {login_response.text}")
            return False
    except Exception as e:
        print(f"   登录失败: {e}")
        return False
    
    # 3. 测试代理API（需要认证）
    print("3. 测试代理API（需要认证）")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        agents_response = requests.get(f"{BASE_URL}/agents", headers=headers, timeout=10)
        print(f"   状态码: {agents_response.status_code}")
        if agents_response.status_code == 200:
            agents_data = agents_response.json()
            print(f"   成功获取代理列表，数量: {len(agents_data)}")
        else:
            print(f"   获取代理列表失败: {agents_response.text}")
    except Exception as e:
        print(f"   代理API测试失败: {e}")
    
    # 4. 测试论文复现API
    print("4. 测试论文复现API")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        papers_response = requests.get(f"{BASE_URL}/paper-reproductions", headers=headers, timeout=10)
        print(f"   状态码: {papers_response.status_code}")
        if papers_response.status_code == 200:
            papers_data = papers_response.json()
            print(f"   成功获取论文列表，数量: {len(papers_data)}")
        else:
            print(f"   获取论文列表失败: {papers_response.text}")
    except Exception as e:
        print(f"   论文API测试失败: {e}")
    
    # 5. 测试模拟生成API（AI模拟平台核心功能）
    print("5. 测试模拟生成API")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        sim_data = {
            "name": "测试模拟",
            "description": "这是一个测试模拟",
            "topic": "测试主题"
        }
        sim_response = requests.post(f"{BASE_URL}/simulations/generate", json=sim_data, headers=headers, timeout=30)
        print(f"   状态码: {sim_response.status_code}")
        if sim_response.status_code == 200:
            sim_result = sim_response.json()
            print(f"   模拟生成成功，ID: {sim_result.get('id', '未知')}")
        else:
            print(f"   模拟生成失败: {sim_response.text}")
    except Exception as e:
        print(f"   模拟生成测试失败: {e}")
    
    print("\n=== API测试完成 ===")
    return True

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)