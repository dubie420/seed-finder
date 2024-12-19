import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import queue
import logging
import json
import datetime
import os
from hashlib import sha3_256, sha256
import secrets
import binascii
from numba import cuda
import numpy as np
import asyncio 
from aiohttp import TCPConnector, ClientSession



class WalletFinderGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Blockchain Wallet Finder")
        self.root.geometry("800x600")
        
        # Create display area
        self.tree = ttk.Treeview(self.root)
        self.tree["columns"] = ("Seed", "Chain", "Balance", "USD Value")
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("Seed", width=300)
        self.tree.column("Chain", width=100)
        self.tree.column("Balance", width=150)
        self.tree.column("USD Value", width=150)
        
        self.tree.heading("Seed", text="Seed Phrase")
        self.tree.heading("Chain", text="Blockchain")
        self.tree.heading("Balance", text="Balance")
        self.tree.heading("USD Value", text="USD Value")
        
        self.tree.pack(pady=20, padx=20, fill='both', expand=True)
        
        # Status label
        self.status_label = tk.Label(self.root, text="Checking: 0 wallets")
        self.status_label.pack(pady=10)
        
        self.found_wallets = []

def save_wallet(wallet_data):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"found_wallets_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(wallet_data, f, indent=4)

def generate_and_check_mnemonic(word_list, exclusions, gui):
    attempts = 0
    while True:
        attempts += 1
        mnemonic = [secrets.choice(word_list) for _ in range(12)]
        mnemonic_phrase = " ".join(mnemonic)
        is_valid, _ = validate_mnemonic(mnemonic_phrase, word_list)
        
        if is_valid:
            # Check all blockchains with this seed
            active_wallets = check_blockchain_balances(mnemonic_phrase)
            if active_wallets:
                wallet_data = {
                    'seed': mnemonic_phrase,
                    'wallets': active_wallets,
                    'timestamp': str(datetime.datetime.now())
                }
                gui.found_wallets.append(wallet_data)
                save_wallet(wallet_data)
                
                # Update GUI
                for chain, data in active_wallets.items():
                    gui.tree.insert("", tk.END, values=(
                        mnemonic_phrase,
                        chain,
                        f"{data['native']['balance_formatted']} {data['native']['symbol']}",
                        f"${data['native']['usd_value']:.2f}"
                    ))
            
            if attempts % 100 == 0:
                gui.status_label.config(text=f"Checked: {attempts} wallets")
                gui.root.update()

if __name__ == "__main__":
    gui = WalletFinderGUI()
    bip39_word_list = load_bip39_wordlist()
    
    if not bip39_word_list:
        exit("Failed to load BIP-39 word list.")
    
    try:
        generate_and_check_mnemonic(bip39_word_list, [], gui)
    except KeyboardInterrupt:
        print("\nSearch stopped by user.")
    
    gui.root.mainloop()


# Load the BIP-39 word list (URL or local file assumed)
def load_bip39_wordlist():
    url = "https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt"
    try:
        import requests
        response = requests.get(url)
        response.raise_for_status()
        return response.text.splitlines()
    except ImportError:
        print("Please install 'requests' library for fetching wordlist!")
        return None

# Generate a secure mnemonic excluding specific words
def generate_mnemonic(word_list, exclusions, word_count=12):
    filtered_word_list = [word for word in word_list if word not in exclusions]
    if len(filtered_word_list) < word_count:
        raise ValueError("Insufficient words after exclusions for the required mnemonic length.")
    
    while True:  # Ensure only valid mnemonics are generated
        mnemonic = [secrets.choice(filtered_word_list) for _ in range(word_count)]
        mnemonic_phrase = " ".join(mnemonic)
        is_valid, _ = validate_mnemonic(mnemonic_phrase, word_list)
        if is_valid:
            return mnemonic_phrase

# Validate the legitimacy of a mnemonic
def validate_mnemonic(mnemonic, word_list):
    # Step 1: Check word count
    words = mnemonic.split()
    if len(words) not in [12, 15, 18, 21, 24]:
        return False, "Invalid word count. Must be 12, 15, 18, 21, or 24 words."
    
    # Step 2: Check if all words are in the BIP-39 word list
    if any(word not in word_list for word in words):
        return False, "Mnemonic contains invalid words."
    
    # Step 3: Decode mnemonic into entropy and checksum
    indices = [word_list.index(word) for word in words]
    binary_str = ''.join(format(index, '011b') for index in indices)
    
    entropy_bits_length = len(binary_str) - len(binary_str) // 33
    entropy_bits = binary_str[:entropy_bits_length]
    checksum_bits = binary_str[entropy_bits_length:]
    
    entropy_bytes = int(entropy_bits, 2).to_bytes(len(entropy_bits) // 8, 'big')
    hash_checksum = hashlib.sha256(entropy_bytes).hexdigest()
    calculated_checksum_bits = bin(int(hash_checksum, 16))[2:].zfill(256)[:len(checksum_bits)]
    
    if checksum_bits != calculated_checksum_bits:
        return False, "Checksum validation failed."
    
    return True, "Valid mnemonic."

# Testing function
def test_mnemonic_generator():
    print("Running Tests...")
    
    # Load wordlist for testing
    word_list = load_bip39_wordlist()
    if not word_list:
        print("Failed to load BIP-39 word list. Testing aborted.")
        return
    
    # Test case 1: Basic generation with no exclusions
    try:
        mnemonic = generate_mnemonic(word_list, exclusions=[])
        print("Test 1 Passed: Generated mnemonic:", mnemonic)
    except Exception as e:
        print("Test 1 Failed:", e)
    
    # Test case 2: Exclusions with sufficient remaining words
    exclusions = word_list[:10]  # Exclude the first 10 words
    try:
        mnemonic = generate_mnemonic(word_list, exclusions=exclusions)
        excluded_check = all(word not in exclusions for word in mnemonic.split())
        if excluded_check:
            print("Test 2 Passed: Exclusions respected.")
        else:
            print("Test 2 Failed: Excluded words found in mnemonic.")
    except Exception as e:
        print("Test 2 Failed:", e)
    
    # Test case 3: Exclusions with insufficient remaining words
    exclusions = word_list[:-11]  # Exclude all but 10 words
    try:
        mnemonic = generate_mnemonic(word_list, exclusions=exclusions)
        print("Test 3 Failed: Expected ValueError, but mnemonic was generated.")
    except ValueError:
        print("Test 3 Passed: Correctly raised ValueError for insufficient words.")
    except Exception as e:
        print("Test 3 Failed:", e)

if __name__ == "__main__":
    # Step 1: Load the word list
    bip39_word_list = load_bip39_wordlist()
    if not bip39_word_list:
        exit("Failed to load BIP-39 word list.")
    
    # Step 2: Excluded words
    excluded_words = input("Enter words to exclude (comma-separated): ").split(",")
    excluded_words = [word.strip() for word in excluded_words]
    
    # Step 3: Generate mnemonic
    try:
        mnemonic = generate_mnemonic(bip39_word_list, excluded_words)
        print(f"Your BIP-39 mnemonic is:\n{mnemonic}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Step 4: Run tests
    test_mnemonic_generator()
import hashlib
import secrets
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
import time

BLOCKCHAIN_APIS = {
    'BTC': {
        'url': 'https://blockchain.info/rawaddr/{}',
        'key': None,
        'backup_url': 'https://api.blockchair.com/bitcoin/dashboards/address/{}'
    },
    'ETH': {
        'url': 'https://api.etherscan.io/api',
        'key': 'RAUWMRX4JYVQGPB3VN9MCQE6DMXP8ZXHGK'
    },
    'BSC': {
        'url': 'https://api.bscscan.com/api',
        'key': 'K7QVKN5724PUXUEM8GQWP5TQVKQQ1YE9G'
    },
    'MATIC': {
        'url': 'https://api.polygonscan.com/api',
        'key': 'XQVB3DXKGVRSZP5FYNK41WUQD8VQWX4MQY'
    },
    'AVAX': {
        'url': 'https://api.snowtrace.io/api',
        'key': 'WXY5YGPJ2NK8DNRH4DSKQTPB9MBQZ6EUHV'
    },
    'FTM': {
        'url': 'https://api.ftmscan.com/api',
        'key': 'H8XVKP2RNQZ5YMWG4DBFJ9TUAS6E3QNMC'
    },
    'ARBITRUM': {
        'url': 'https://api.arbiscan.io/api',
        'key': 'TQNKX5RVDP8MYHW2GBFJ4UEAS9Z6CQMV3'
    },
    'OPTIMISM': {
        'url': 'https://api-optimistic.etherscan.io/api',
        'key': 'M9RKNX4YPWH2VBQT8GJUE5AS7D3ZCQF6V'
    },
    'CRONOS': {
        'url': 'https://api.cronoscan.com/api',
        'key': 'VBQT8GJUE5AS7D3ZCQF6VM9RKNX4YPWH2'
    },
    'SOLANA': {
        'url': 'https://api.solscan.io/account/{}',
        'key': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.solscan.api.key'
    }
}

def load_bip39_wordlist():
    url = "https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt"
    response = requests.get(url)
    return response.text.splitlines()

class TokenBalance:
    def __init__(self, chain: str, address: str):
        self.chain = chain
        self.address = address
        self.api_config = BLOCKCHAIN_APIS[chain]

    def get_native_balance(self) -> Dict:
        if self.chain == 'BTC':
            try:
                response = requests.get(self.api_config['url'].format(self.address))
                if response.status_code == 200:
                    data = response.json()
                    balance = data['final_balance']
                    return {
                        'symbol': 'BTC',
                        'balance': balance,
                        'balance_formatted': balance / 1e8,
                        'usd_value': self._get_price('BTC') * (balance / 1e8)
                    }
            except:
                try:
                    response = requests.get(self.api_config['backup_url'].format(self.address))
                    if response.status_code == 200:
                        data = response.json()
                        balance = data['data'][self.address]['address']['balance']
                        return {
                            'symbol': 'BTC',
                            'balance': balance,
                            'balance_formatted': balance / 1e8,
                            'usd_value': self._get_price('BTC') * (balance / 1e8)
                        }
                except:
                    return None
        elif self.chain == 'SOLANA':
            headers = {'Authorization': f'Bearer {self.api_config["key"]}'}
            response = requests.get(self.api_config['url'].format(self.address), headers=headers)
            if response.status_code == 200:
                data = response.json()
                balance = int(data.get('lamports', 0))
                return {
                    'symbol': 'SOL',
                    'balance': balance,
                    'balance_formatted': balance / 1e9,
                    'usd_value': self._get_price('SOL') * (balance / 1e9)
                }
        else:
            params = {
                'module': 'account',
                'action': 'balance',
                'address': self.address,
                'apikey': self.api_config['key']
            }
            response = requests.get(self.api_config['url'], params=params)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    balance = int(data['result'])
                    return {
                        'symbol': self.chain,
                        'balance': balance,
                        'balance_formatted': balance / 1e18,
                        'usd_value': self._get_price(self.chain) * (balance / 1e18)
                    }
        return None
def get_native_balance(self) -> Dict:
    if self.chain == 'ETH':
        # Primary endpoint
        url = f"https://api.etherscan.io/api"
        params = {
            'module': 'account',
            'action': 'balance',
            'address': self.address,
            'apikey': self.api_config['key'],
            'tag': 'latest'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }
        
        try:
            session = requests.Session()
            response = session.get(url, params=params, headers=headers, verify=True, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    balance = int(data['result'])
                    return {
                        'symbol': 'ETH',
                        'balance': balance,
                        'balance_formatted': balance / 1e18,
                        'usd_value': self._get_price('ETH') * (balance / 1e18)
                    }
            
            # Backup endpoint if primary fails
            backup_url = f"https://eth-mainnet.g.alchemy.com/v2/{self.api_config['backup_key']}"
            response = session.post(backup_url, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[self.address,"latest"],"id":1})
            if response.status_code == 200:
                balance = int(response.json()['result'], 16)
                return {
                    'symbol': 'ETH',
                    'balance': balance,
                    'balance_formatted': balance / 1e18,
                    'usd_value': self._get_price('ETH') * (balance / 1e18)
                }
        except Exception as e:
            time.sleep(1)  # Rate limiting
            return None

    def get_token_balances(self) -> List[Dict]:
        tokens = []
        if self.chain in ['ETH', 'BSC', 'MATIC', 'AVAX', 'FTM', 'ARBITRUM', 'OPTIMISM', 'CRONOS']:
            params = {
                'module': 'account',
                'action': 'tokenbalance',
                'address': self.address,
                'apikey': self.api_config['key']
            }
            response = requests.get(self.api_config['url'], params=params)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == '1':
                    for token in data.get('result', []):
                        balance = int(token['balance'])
                        if balance > 0:
                            tokens.append({
                                'symbol': token['tokenSymbol'],
                                'balance': balance,
                                'balance_formatted': balance / (10 ** int(token['tokenDecimal'])),
                                'contract': token['contractAddress']
                            })
        return tokens

    def _get_price(self, symbol: str) -> float:
        try:
            response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd')
            if response.status_code == 200:
                return response.json()[symbol.lower()]['usd']
        except:
            return 0
        return 0

def validate_mnemonic(mnemonic, word_list):
    words = mnemonic.split()
    if len(words) not in [12, 15, 18, 21, 24]:
        return False, "Invalid word count"
    
    if any(word not in word_list for word in words):
        return False, "Invalid words"
    
    return True, "Valid mnemonic"

def check_blockchain_balances(mnemonic: str) -> Dict:
    active_wallets = {}
    
    def check_chain(chain):
        try:
            address = f"SAMPLE_ADDRESS_{chain}"  # Replace with actual derivation
            token_checker = TokenBalance(chain, address)
            
            native_balance = token_checker.get_native_balance()
            if native_balance:
                active_wallets[chain] = {
                    'address': address,
                    'native': native_balance,
                    'tokens': token_checker.get_token_balances()
                }
            
            time.sleep(0.2)
        except Exception as e:
            print(f"Error checking {chain}: {str(e)}")
    
    with ThreadPoolExecutor(max_workers=len(BLOCKCHAIN_APIS)) as executor:
        executor.map(check_chain, BLOCKCHAIN_APIS.keys())
    
    return active_wallets

def generate_mnemonic(word_list, exclusions, word_count=12):
    filtered_word_list = [word for word in word_list if word not in exclusions]
    if len(filtered_word_list) < word_count:
        raise ValueError("Insufficient words after exclusions")
    
    attempts = 0
    while True:
        attempts += 1
        mnemonic = [secrets.choice(filtered_word_list) for _ in range(word_count)]
        mnemonic_phrase = " ".join(mnemonic)
        is_valid, _ = validate_mnemonic(mnemonic_phrase, word_list)
        
        if is_valid:
            active_wallets = check_blockchain_balances(mnemonic_phrase)
            if active_wallets:
                print_wallet_info(mnemonic_phrase, active_wallets, attempts)
                return mnemonic_phrase
            
            if attempts % 100 == 0:
                print(f"Checked {attempts} wallets...")

def print_wallet_info(mnemonic: str, active_wallets: Dict, attempts: int):
    print(f"\n=== FOUND ACTIVE WALLET (Attempt #{attempts}) ===")
    print(f"Seed Phrase: {mnemonic}")
    print("\nBalances:")
    
    total_usd_value = 0
    for chain, data in active_wallets.items():
        print(f"\n{chain}:")
        print(f"  Address: {data['address']}")
        

connector = TCPConnector(limit=100, ttl_dns_cache=300)
session = ClientSession(connector=connector)

DARK_THEME = {
    'bg': '#2b2b2b',
    'fg': '#ffffff',
    'select_bg': '#404040',
    'tree_bg': '#333333',
    'button_bg': '#404040',
    'button_fg': '#ffffff',
    'menu_bg': '#333333',
    'menu_fg': '#ffffff'
}                                                                                                                                        
class NetworkOptimizer:
    def __init__(self):
        self.connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
        self.session_timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.batch_size = 10000  # Increased for 1Gbps
        self.max_concurrent = 200  # Maximized concurrent connections
        self.headers = {
            'Connection': 'keep-alive',
            'Keep-Alive': '300',
            'User-Agent': 'Mozilla/5.0'
        }

    async def process_network_batch(self, addresses):
        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.session_timeout,
            headers=self.headers
        ) as session:
            tasks = []
            for addr_chunk in np.array_split(addresses, len(addresses) // self.batch_size):
                tasks.extend([self.check_address(session, addr) for addr in addr_chunk])
            return await asyncio.gather(*tasks, return_exceptions=True)

class AsyncClient:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.session = None
        self.connector = aiohttp.TCPConnector(
            limit=0,
            ttl_dns_cache=300,
            use_dns_cache=True,
            force_close=False
        )
        
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()
        await self.connector.close()

class WalletProcessor:
    def __init__(self):
        self.client = AsyncClient()
        
    @staticmethod
    def generate_wallet():
        seed = secrets.token_bytes(32)
        private_key = sha3_256(seed).digest()
        address = "0x" + binascii.hexlify(sha3_256(private_key).digest()[-20:]).decode('utf-8')
        return {
            'address': address,
            'private_key': binascii.hexlify(private_key).decode('utf-8'),
            'seed': binascii.hexlify(seed).decode('utf-8')
        }

class WalletFinderGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Blockchain Wallet Finder")
        self.root.geometry("1000x800")
        
        # Initialize components
        self.setup_logging()
        self.setup_variables()
        self.setup_gui_components()
        self.create_menu()
        
        # Apply dark theme
        self.apply_dark_theme()
        
        # Initialize processor
        self.wallet_processor = WalletProcessor()
        
        # Start GUI update loop
        self.root.after(100, self.update_gui)

    def apply_dark_theme(self):
        self.root.configure(bg=DARK_THEME['bg'])
        style = ttk.Style()
        style.configure('Dark.TFrame', background=DARK_THEME['bg'])
        style.configure('Dark.TLabel', background=DARK_THEME['bg'], foreground=DARK_THEME['fg'])
        style.configure('Treeview', 
                       background=DARK_THEME['tree_bg'],
                       foreground=DARK_THEME['fg'],
                       fieldbackground=DARK_THEME['tree_bg'])

    def setup_logging(self):
        logging.basicConfig(
            filename='wallet_finder.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S:%f'
        )

    def setup_variables(self):
        self.running = threading.Event()
        self.update_queue = queue.Queue()
        self.total_checked = 0
        self.found_wallets = []

    def setup_gui_components(self):
        self.main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Status section
        self.status_frame = ttk.LabelFrame(self.main_frame, text="Status", style='Dark.TFrame')
        self.status_frame.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack(pady=5)
        
        # Progress section
        self.progress_var = tk.StringVar(value="Wallets checked: 0")
        self.progress_label = ttk.Label(self.main_frame, textvariable=self.progress_var)
        self.progress_label.pack(pady=5)
        
        self.create_results_tree()

    def create_menu(self):
        menubar = tk.Menu(self.root, bg=DARK_THEME['menu_bg'], fg=DARK_THEME['menu_fg'])
        self.root.config(menu=menubar)
        
        control_menu = tk.Menu(menubar, tearoff=0, bg=DARK_THEME['menu_bg'], fg=DARK_THEME['menu_fg'])
        menubar.add_cascade(label="Control", menu=control_menu)
        control_menu.add_command(label="Start", command=self.start_search)
        control_menu.add_command(label="Stop", command=self.stop_search)

    def create_results_tree(self):
        columns = ("Timestamp", "Address", "Balance", "Status")
        self.tree = ttk.Treeview(self.main_frame, columns=columns, show='headings')
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
            
        scrollbar = ttk.Scrollbar(self.main_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def start_search(self):
        if not self.running.is_set():
            self.running.set()
            threading.Thread(target=self.search_wallets, daemon=True).start()
            self.status_var.set("Search started...")

    def stop_search(self):
        if self.running.is_set():
            self.running.clear()
            self.status_var.set("Search stopped")

    def search_wallets(self):
        with ThreadPoolExecutor(max_workers=16) as executor:
            while self.running.is_set():
                try:
                    wallet = self.wallet_processor.generate_wallet()
                    self.total_checked += 1
                    
                    if self.total_checked % 100 == 0:
                        self.progress_var.set(f"Wallets checked: {self.total_checked:,}")
                        
                except Exception as e:
                    logging.error(f"Search error: {str(e)}")
                    time.sleep(1)

    def update_gui(self):
        try:
            while True:
                func, args = self.update_queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_gui)

    def run(self):
        self.root.mainloop()

def main():
    app = WalletFinderGUI()
    app.run()

if __name__ == "__main__":
    main()
