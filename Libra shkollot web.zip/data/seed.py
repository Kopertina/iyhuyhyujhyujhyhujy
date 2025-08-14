import os
import sqlite3

BASE = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE, 'data', 'bookstore.db')
os.makedirs(os.path.join(BASE, 'data'), exist_ok=True)

schema = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  author TEXT,
  grade INTEGER NOT NULL,
  price REAL NOT NULL,
  image_url TEXT,
  description TEXT,
  stock INTEGER DEFAULT 100
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  address TEXT NOT NULL,
  note TEXT,
  total_price REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  title_snapshot TEXT,
  FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

sample_products = [
    # grade, title, author, price
    (1, "Abetare", "Grupi Autorëve", 4.50),
    (1, "Matematikë 1", "A. Hoxha", 5.90),
    (2, "Gjuha Shqipe 2", "M. Krasniqi", 6.20),
    (2, "Matematikë 2", "R. Berisha", 6.50),
    (3, "Dituri Natyre 3", "E. Dervishi", 7.00),
    (3, "Leximi 3", "N. Gashi", 6.80),
    (4, "Gjuha Shqipe 4", "A. Islami", 7.20),
    (4, "Matematikë 4", "L. Shala", 7.40),
    (5, "Histori 5", "K. Rexhepi", 8.30),
    (5, "Gjeografi 5", "B. Peci", 8.10),
    (6, "Biologji 6", "D. Sahiti", 9.20),
    (6, "Fizikë 6", "A. Aliu", 9.50),
    (7, "Kimi 7", "E. Mustafa", 10.20),
    (7, "Letërsi 7", "R. Krasniqi", 10.00),
    (8, "Matematikë 8", "S. Hoxha", 11.50),
    (8, "Gjeometri 8", "M. Mehmeti", 11.00),
    (9, "Fizikë 9", "L. Berisha", 12.40),
    (9, "Gjuha Shqipe 9", "V. Hoti", 12.00),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(schema)
    cur.execute("DELETE FROM products")
    for grade, title, author, price in sample_products:
        cur.execute("""
            INSERT INTO products (title, author, grade, price, image_url, description, stock)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title, author, grade, price,
            "https://via.placeholder.com/300x400?text=Liber",
            f"Liber mësimor për klasën {grade}.",
            100
        ))
    conn.commit()
    conn.close()
    print("Database seeded with sample products.")

if __name__ == "__main__":
    seed()