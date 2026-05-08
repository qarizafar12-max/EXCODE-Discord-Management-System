import sqlite3

conn = sqlite3.connect('bot_database.db')
c = conn.cursor()

ticket_id = 1461652379370918073

# Check ticket
c.execute('SELECT channel_id, status FROM tickets WHERE channel_id = ?', (ticket_id,))
r = c.fetchone()
print(f'Ticket {ticket_id}:')
print(f'  Status: {r[1] if r else "NOT FOUND"}')

# Check messages
c.execute('SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = ?', (ticket_id,))
count = c.fetchone()[0]
print(f'  Messages logged: {count}')

# Show messages
c.execute('SELECT author_name, content, timestamp FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp', (ticket_id,))
messages = c.fetchall()
print(f'\n  Message history:')
for m in messages:
    content = (m[1] if m[1] else '(empty)')[:50]
    print(f'    [{m[2]}] {m[0]}: {content}')

conn.close()
