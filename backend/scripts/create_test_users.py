"""创建测试用户：admin 和 test 用户"""
import asyncio
import hashlib
from database import get_db, init_db
import config


def _hash_password(password: str) -> str:
    return hashlib.sha256((password + config.JWT_SECRET).encode()).hexdigest()


async def create_test_users():
    await init_db()
    db = await get_db()
    
    try:
        # 创建 admin 用户
        admin_password = _hash_password("admin123")
        await db.execute(
            """INSERT OR IGNORE INTO users 
               (openid, phone, password_hash, nickname, login_type, is_member, is_admin) 
               VALUES (?, ?, ?, ?, 'phone', 1, 1)""",
            ("phone_admin", "13800000001", admin_password, "管理员",)
        )
        
        # 创建测试用户
        test_password = _hash_password("test123")
        await db.execute(
            """INSERT OR IGNORE INTO users 
               (openid, phone, password_hash, nickname, login_type, is_member, is_admin) 
               VALUES (?, ?, ?, ?, 'phone', 0, 0)""",
            ("phone_test", "13800000002", test_password, "测试用户",)
        )
        
        await db.commit()
        
        # 查询创建的用户
        async with db.execute("SELECT id, phone, nickname, is_member, is_admin FROM users WHERE phone IN ('13800000001', '13800000002')") as cur:
            users = await cur.fetchall()
        
        print("\n=== 测试用户创建完成 ===")
        for u in users:
            print(f"ID: {u[0]}, 手机: {u[1]}, 昵称: {u[2]}, 会员: {u[3]}, 管理员: {u[4]}")
        
        print("\n登录信息:")
        print("管理员: 13800000001 / admin123")
        print("测试用户: 13800000002 / test123")
        
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(create_test_users())
