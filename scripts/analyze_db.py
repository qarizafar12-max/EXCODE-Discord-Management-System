import sqlite3

conn = sqlite3.connect('bot_database.db')
c = conn.cursor()

print('===== COMPLETE ANALYSIS =====\n')

# 1. All tickets
print('1. ALL TICKETS (latest 10):')
c.execute('SELECT channel_id, status, created_at FROM tickets ORDER BY created_at DESC LIMIT 10')
for r in c.fetchall():
    print(f'   Channel: {r[0]} | Status: {r[1]} | Created: {r[2]}')

# 2. Open tickets
print('\n2. OPEN TICKETS:')
c.execute('SELECT channel_id FROM tickets WHERE status=?', ('open',))
open_tickets = c.fetchall()
if not open_tickets:
    print('   None')
else:
    for r in open_tickets:
        print(f'   {r[0]}')

# 3. Message queue
print('\n3. MESSAGE QUEUE (last 10 tasks):')
c.execute('SELECT id, action_type, payload, status FROM message_queue ORDER BY id DESC LIMIT 10')
for r in c.fetchall():
    print(f'   Task {r[0]}: {r[1]} | Status: {r[3]} | Payload: {r[2][:60]}...')

# 4. Ticket messages  
print('\n4. TICKET MESSAGES (last 10):')
c.execute('SELECT ticket_id, author_name, content, timestamp FROM ticket_messages ORDER BY id DESC LIMIT 10')
messages = c.fetchall()
if not messages:
    print('   None')
else:
    for r in messages:
        content = r[2] if r[2] else '(empty)'
        print(f'   Ticket {r[0]}: {r[1]} - {content[:40]}... @ {r[3]}')

# 5. Message count per ticket
print('\n5. MESSAGE COUNT PER TICKET:')
c.execute('SELECT ticket_id, COUNT(*) FROM ticket_messages GROUP BY ticket_id')
for r in c.fetchall():
    print(f'   Ticket {r[0]}: {r[1]} messages')

conn.close()

print('\n===== ANALYSIS COMPLETE =====')
