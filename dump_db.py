import sqlite3
import io

def dump_db():
    try:
        conn = sqlite3.connect('nexpos.db')
        
        # Open the output file
        with io.open('nexpos_model_v2_2.sql', 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write('%s\n' % line)
                
        print("Database dumped successfully to nexpos_model_v2_2.sql")
        conn.close()
    except Exception as e:
        print(f"Error dumping database: {e}")

if __name__ == "__main__":
    dump_db()
