import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///storage.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_bot2_update():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            print("🛠 Updating Database for Bot 2...")

            # 1. Update BotUsers Table (Warnings & Bans)
            try:
                if "sqlite" in DATABASE_URL:
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN warning_count INTEGER DEFAULT 0;"))
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN is_global_banned BOOLEAN DEFAULT 0;"))
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN restricted_until DATETIME;"))
                else:
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS warning_count INTEGER DEFAULT 0;"))
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS is_global_banned BOOLEAN DEFAULT FALSE;"))
                    conn.execute(text("ALTER TABLE bot_users ADD COLUMN IF NOT EXISTS restricted_until TIMESTAMP;"))
                print("✅ Added Bot 2 columns to bot_users")
            except Exception as e:
                print(f"ℹ️ Bot 2 columns skipped (shayad pehle se hain): {e}")

            # 2. Create New Tables
            if "sqlite" in DATABASE_URL:
                conn.execute(text("CREATE TABLE IF NOT EXISTS group_settings (id INTEGER PRIMARY KEY, chat_id INTEGER UNIQUE, welcome_enabled BOOLEAN DEFAULT 1, rules_text TEXT, anti_link BOOLEAN DEFAULT 1, anti_flood BOOLEAN DEFAULT 1);"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS admin_permissions (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, can_ban BOOLEAN DEFAULT 0, can_warn BOOLEAN DEFAULT 0, can_change_settings BOOLEAN DEFAULT 0);"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS auto_replies (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE, reply_text TEXT);"))
            else:
                conn.execute(text("CREATE TABLE IF NOT EXISTS group_settings (id SERIAL PRIMARY KEY, chat_id BIGINT UNIQUE, welcome_enabled BOOLEAN DEFAULT TRUE, rules_text TEXT, anti_link BOOLEAN DEFAULT TRUE, anti_flood BOOLEAN DEFAULT TRUE);"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS admin_permissions (id SERIAL PRIMARY KEY, user_id BIGINT UNIQUE, can_ban BOOLEAN DEFAULT FALSE, can_warn BOOLEAN DEFAULT FALSE, can_change_settings BOOLEAN DEFAULT FALSE);"))
                conn.execute(text("CREATE TABLE IF NOT EXISTS auto_replies (id SERIAL PRIMARY KEY, keyword VARCHAR(255) UNIQUE, reply_text TEXT);"))
            
            print("✅ Created new tables for Bot 2")
            trans.commit()
            print("\n🎉 SUCCESS! Bot 2 Database is ready.")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    run_bot2_update()
