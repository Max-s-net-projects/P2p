import socket
import json
import uuid
import threading
import time
import sys
import pickle
import os
import select
from datetime import datetime

class PureP2PNetwork:
    def __init__(self):
        self.username = None
        self.node_id = str(uuid.uuid4())[:8]
        self.port = 55888
        self.peers = {}  # active connections
        self.friends = {}  # username -> connection_info
        self.friend_requests = {}  # incoming requests
        self.conversations = {}  # all chat history
        self.running = True
        self.current_chat = None
        
        # Data storage
        self.data_file = "p2p_data.pkl"
        self.load_data()
        
        # Setup networking
        self.setup_sockets()
    
    def setup_sockets(self):
        """Setup TCP server for incoming connections"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(10)
            self.server_socket.settimeout(1.0)
            print(f"🔌 P2P Node listening on port {self.port}")
        except Exception as e:
            print(f"❌ Failed to bind port {self.port}: {e}")
            sys.exit(1)
    
    def load_data(self):
        """Load saved friends and conversations"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'rb') as f:
                    data = pickle.load(f)
                    self.friends = data.get('friends', {})
                    self.conversations = data.get('conversations', {})
                    self.friend_requests = data.get('friend_requests', {})
                print(f"✅ Loaded {len(self.friends)} friends and {len(self.conversations)} conversations")
            except Exception as e:
                print("⚠️  Could not load previous data")
    
    def save_data(self):
        """Save all data"""
        try:
            data = {
                'friends': self.friends,
                'conversations': self.conversations,
                'friend_requests': self.friend_requests
            }
            with open(self.data_file, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass
    
    def setup_username(self):
        """User registration"""
        while True:
            username = input("Choose your username: ").strip()
            if username and 3 <= len(username) <= 20:
                self.username = username
                print(f"✅ Username: {username}")
                print(f"🆔 Node ID: {self.node_id}")
                return
            else:
                print("❌ Username must be 3-20 characters")
    
    def start_network(self):
        """Start all network services"""
        # Start TCP server
        server_thread = threading.Thread(target=self.tcp_server, daemon=True)
        server_thread.start()
        
        print("🌍 P2P Network Started!")
        print("💡 Type 'help' for commands")
    
    def tcp_server(self):
        """Handle incoming connections"""
        while self.running:
            try:
                readable, _, _ = select.select([self.server_socket], [], [], 1.0)
                if readable:
                    client_socket, addr = self.server_socket.accept()
                    threading.Thread(target=self.handle_connection, args=(client_socket,), daemon=True).start()
            except:
                pass
    
    def handle_connection(self, client_socket):
        """Handle incoming connection"""
        try:
            data = client_socket.recv(4096).decode()
            if data:
                message = json.loads(data)
                self.process_incoming_message(message, client_socket)
        except:
            pass
        finally:
            client_socket.close()
    
    def process_incoming_message(self, message, sock):
        """Process incoming messages"""
        msg_type = message.get('type')
        
        if msg_type == 'friend_request':
            from_user = message['from_user']
            from_ip = message['from_ip']
            from_port = message['from_port']
            
            print(f"\n📨 Friend request from {from_user}")
            response = input("Accept? (y/n): ").lower().strip()
            
            if response == 'y':
                # Add to friends
                self.friends[from_user] = {
                    'ip': from_ip,
                    'port': from_port,
                    'connected': True
                }
                self.save_data()
                
                # Send acceptance
                self.send_direct_message(from_ip, from_port, {
                    'type': 'friend_accept',
                    'from_user': self.username
                })
                print(f"✅ {from_user} is now your friend!")
            else:
                # Send rejection
                self.send_direct_message(from_ip, from_port, {
                    'type': 'friend_reject',
                    'from_user': self.username
                })
                print(f"❌ Rejected {from_user}")
            
            print("p2p> ", end="", flush=True)
                
        elif msg_type == 'friend_accept':
            from_user = message['from_user']
            print(f"\n✅ {from_user} accepted your friend request!")
            print("p2p> ", end="", flush=True)
            
        elif msg_type == 'friend_reject':
            from_user = message['from_user']
            print(f"\n❌ {from_user} rejected your friend request")
            print("p2p> ", end="", flush=True)
            
        elif msg_type == 'chat_message':
            from_user = message['from_user']
            content = message['content']
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Store message
            if from_user not in self.conversations:
                self.conversations[from_user] = []
            
            self.conversations[from_user].append({
                'time': timestamp,
                'from': from_user,
                'content': content,
                'direction': 'incoming'
            })
            self.save_data()
            
            # Show notification if not in chat with this user
            if self.current_chat != from_user:
                print(f"\n📨 [{timestamp}] {from_user}: {content}")
            print("p2p> ", end="", flush=True)
    
    def send_direct_message(self, ip, port, message):
        """Send direct TCP message to peer"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            sock.send(json.dumps(message).encode())
            sock.close()
            return True
        except:
            return False
    
    def add_friend(self, username, ip, port):
        """Send friend request"""
        success = self.send_direct_message(ip, port, {
            'type': 'friend_request',
            'from_user': self.username,
            'from_ip': self.get_local_ip(),
            'from_port': self.port
        })
        
        if success:
            print(f"📨 Friend request sent to {username}")
            # Store pending request
            self.friend_requests[username] = (ip, port)
            self.save_data()
        else:
            print(f"❌ Could not connect to {username}")
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def search_and_add(self, query=None):
        """Search and add friends manually"""
        if query:
            print(f"🔍 Searching for friends with '{query}'...")
        else:
            print("👥 Add friends manually:")
        
        print("\nTo add a friend, you need their:")
        print("1. IP address (get this from them)")
        print("2. Port (usually 55888)")
        print("3. Username (exact spelling)")
        
        ip = input("Enter friend's IP: ").strip()
        port = input("Enter friend's port (55888): ").strip()
        username = input("Enter friend's username: ").strip()
        
        if not port:
            port = 55888
        else:
            port = int(port)
        
        if ip and username:
            self.add_friend(username, ip, port)
        else:
            print("❌ IP and username are required")
    
    def show_friends(self):
        """Show all friends"""
        if not self.friends:
            print("❌ No friends yet. Use 'add' to add friends.")
            return
        
        print("\n👥 Your Friends:")
        print("-" * 40)
        for username, info in self.friends.items():
            status = "🟢" if info.get('connected', False) else "🔴"
            print(f"{status} {username}")
        print("-" * 40)
    
    def chat_with_friend(self, username):
        """Start chat with friend"""
        if username not in self.friends:
            print(f"❌ {username} is not your friend. Use 'add' first.")
            return
        
        friend_info = self.friends[username]
        self.current_chat = username
        
        print(f"\n💬 Chat with {username} (type 'exit' to leave)")
        print("-" * 50)
        
        # Show conversation history
        self.show_conversation(username)
        
        while self.current_chat == username:
            try:
                message = input().strip()
                
                if message.lower() == 'exit':
                    self.current_chat = None
                    print("👋 Left chat")
                    break
                
                if message:
                    # Send message
                    success = self.send_direct_message(
                        friend_info['ip'], 
                        friend_info['port'], 
                        {
                            'type': 'chat_message',
                            'from_user': self.username,
                            'content': message
                        }
                    )
                    
                    if success:
                        # Store sent message
                        if username not in self.conversations:
                            self.conversations[username] = []
                        
                        self.conversations[username].append({
                            'time': datetime.now().strftime("%H:%M:%S"),
                            'from': self.username,
                            'content': message,
                            'direction': 'outgoing'
                        })
                        self.save_data()
                        
                        print(f"➤ You: {message}")
                    else:
                        print("❌ Message failed - friend might be offline")
                        self.friends[username]['connected'] = False
                        
            except KeyboardInterrupt:
                self.current_chat = None
                print("\n👋 Left chat")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def show_conversation(self, username):
        """Show chat history with friend"""
        if username in self.conversations and self.conversations[username]:
            for msg in self.conversations[username][-20:]:  # Last 20 messages
                prefix = "➤ You" if msg['direction'] == 'outgoing' else f"◈ {username}"
                print(f"[{msg['time']}] {prefix}: {msg['content']}")
        else:
            print("💬 No messages yet. Start the conversation!")
        print("-" * 50)
    
    def show_help(self):
        """Show available commands"""
        print("\n🛠️  Available Commands:")
        print("  add              - Add a new friend")
        print("  friends          - Show your friends")
        print("  chat <username>  - Start chatting")
        print("  history <user>   - Show message history")
        print("  search <query>   - Search for friends")
        print("  help             - Show this help")
        print("  exit             - Exit the network")
        print("\n💡 How to connect globally:")
        print("1. Share your IP and port with friends")
        print(f"2. Your port: {self.port}")
        print("3. Friends use 'add' command with your info")
        print()
    
    def run(self):
        """Main loop"""
        print("🚀 Starting Pure P2P Network...")
        print("=" * 50)
        
        self.setup_username()
        self.start_network()
        
        # Main command loop
        while self.running:
            try:
                if self.current_chat:
                    # In chat mode, don't show prompt
                    time.sleep(0.1)
                    continue
                    
                command = input("\np2p> ").strip()
                
                if command == 'exit':
                    self.running = False
                    self.save_data()
                    print("👋 Goodbye!")
                    break
                    
                elif command == 'add':
                    self.search_and_add()
                    
                elif command.startswith('search '):
                    query = command[7:].strip()
                    self.search_and_add(query)
                    
                elif command.startswith('chat '):
                    username = command[5:].strip()
                    if username:
                        self.chat_with_friend(username)
                    else:
                        print("❌ Usage: chat username")
                        
                elif command.startswith('history '):
                    username = command[8:].strip()
                    if username:
                        self.show_conversation(username)
                    else:
                        print("❌ Usage: history username")
                        
                elif command == 'friends':
                    self.show_friends()
                    
                elif command == 'help':
                    self.show_help()
                    
                else:
                    print("❌ Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                self.running = False
                self.save_data()
                break
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    node = PureP2PNetwork()
    node.run()
