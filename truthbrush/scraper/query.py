import argparse
import sqlite3
import pprint

from db import get_db_connection

def run_query(query: str):
    """Run a SQL query against the database and print the results."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Determine if it's a SELECT query (returns rows) or an INSERT/UPDATE
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            if not rows:
                print("No results returned.")
            else:
                # get column names
                col_names = [description[0] for description in cursor.description]
                
                # compute max width for each column
                col_widths = [len(str(name)) for name in col_names]
                for row in rows:
                    for i, val in enumerate(row):
                        col_widths[i] = max(col_widths[i], len(str(val)))
                        
                # format string
                fmt = " | ".join([f"{{:<{w}}}" for w in col_widths])
                
                # print header
                print(fmt.format(*col_names))
                print("-" * (sum(col_widths) + 3 * (len(col_widths) - 1)))
                
                # print rows
                for row in rows:
                    print(fmt.format(*(str(v) for v in row)))
                    
                print(f"\n{len(rows)} row(s) returned.")
        else:
            conn.commit()
            print(f"Statement executed successfully. {cursor.rowcount} row(s) affected.")
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the Truthbrush local SQLite database.")
    parser.add_argument("query", type=str, help="The SQL statement to execute. Must be in quotes.")
    args = parser.parse_args()
    
    run_query(args.query)
