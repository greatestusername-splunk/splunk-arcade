#!/usr/bin/env python3
"""
E2E User Load Test - Simulates complete user journey:
1. Registration & Login (Portal)
2. Home page navigation
3. Game selection and loading  
4. Actual gameplay simulation
5. Quiz question answering
6. Game progression unlocking
7. Multi-game navigation flow

This test follows the EXACT user workflow including frontend page loads,
quiz interactions, and progression unlocking sequence.
"""

import asyncio
import aiohttp
import time
import argparse
import random
import string
import re
import json
import ssl
from dataclasses import dataclass
from typing import List, Optional, Dict
from collections import defaultdict


@dataclass
class Player:
    """Individual player with full progression state"""
    username: str
    password: str
    session_cookies: dict
    cabinet_url: Optional[str] = None
    pod_ready: bool = False
    
    # Game progression tracking
    unlocked_games: List[str] = None
    current_game: Optional[str] = None
    games_completed: List[str] = None
    quiz_questions_answered: Dict[str, int] = None
    
    # Performance metrics
    pages_loaded: int = 0
    games_played: int = 0
    quizzes_completed: int = 0
    requests_made: int = 0
    errors: int = 0
    error_details: List[str] = None
    
    def __post_init__(self):
        if self.unlocked_games is None:
            self.unlocked_games = ["imvaders"]  # Start with imvaders unlocked
        if self.games_completed is None:
            self.games_completed = []
        if self.quiz_questions_answered is None:
            self.quiz_questions_answered = defaultdict(int)
        if self.error_details is None:
            self.error_details = []


class End2EndUserTester:
    """Complete user journey load tester with real navigation and progression"""
    
    def __init__(self, portal_url: str = "http://us.splunkarcade.com:80", production: bool = False):
        self.portal_url = portal_url.rstrip('/')
        self.production = production
        self.players: List[Player] = []
        self.created_users: List[str] = []
        
        # Game progression sequence (based on actual scoreboard logic)
        self.game_sequence = ["imvaders", "logger", "bughunt", "floppybird", "zelda"]
        self.quiz_requirements = {
            "imvaders": 6,  # Need 6 questions to unlock logger (final version requirement)
            "logger": 6,    # Need 6 questions to unlock bughunt (final version requirement)  
            "bughunt": 3    # Need fewer questions for final unlock
        }
    
    def generate_valid_username(self, player_id: int) -> str:
        """Generate Kubernetes-compliant username"""
        base = f"loadtest-user-{player_id:03d}"
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
        return f"{base}-{suffix}"
    
    async def register_user(self, session: aiohttp.ClientSession, username: str, password: str) -> bool:
        """Register user through portal with CSRF handling"""
        try:
            async with session.get(f"{self.portal_url}/register") as response:
                if response.status != 200:
                    return False
                
                html_content = await response.text()
                csrf_token = self.extract_csrf_token(html_content)
                
                registration_data = {
                    'username': username,
                    'password': password,
                    'password2': password,
                    'submit': 'Register'
                }
                if csrf_token:
                    registration_data['csrf_token'] = csrf_token
                
                async with session.post(f"{self.portal_url}/register", 
                                      data=registration_data, allow_redirects=False) as reg_response:
                    if reg_response.status == 302 and '/login' in reg_response.headers.get('Location', ''):
                        print(f"✅ Registered user: {username}")
                        self.created_users.append(username)
                        return True
                    return False
                    
        except Exception as e:
            print(f"❌ Registration error for {username}: {e}")
            return False
    
    async def login_user(self, session: aiohttp.ClientSession, player: Player) -> bool:
        """Login user and establish session"""
        try:
            async with session.get(f"{self.portal_url}/login") as response:
                if response.status != 200:
                    return False
                
                html_content = await response.text()
                csrf_token = self.extract_csrf_token(html_content)
            
            login_data = {
                'username': player.username,
                'password': player.password,
                'remember_me': False,
                'submit': 'Sign In'
            }
            if csrf_token:
                login_data['csrf_token'] = csrf_token
            
            async with session.post(f"{self.portal_url}/login", 
                                  data=login_data, allow_redirects=False) as login_response:
                if login_response.status in [200, 302]:
                    cookies = {cookie.key: cookie.value for cookie in session.cookie_jar}
                    player.session_cookies = cookies
                    print(f"✅ Logged in user: {player.username}")
                    return True
                return False
                
        except Exception as e:
            print(f"❌ Login error for {player.username}: {e}")
            return False
    
    def extract_csrf_token(self, html_content: str) -> Optional[str]:
        """Extract CSRF token from HTML"""
        csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html_content)
        return csrf_match.group(1) if csrf_match else None
    
    async def wait_for_cabinet_ready(self, session: aiohttp.ClientSession, player: Player, 
                                   timeout: int = 120) -> bool:
        """Wait for player's cabinet pod to be ready"""
        start_time = time.time()
        expected_cabinet_url = f"{self.portal_url}/player/{player.username}"
        
        while time.time() - start_time < timeout:
            try:
                async with session.get(f"{expected_cabinet_url}/alive", timeout=8) as response:
                    if response.status == 200:
                        player.cabinet_url = expected_cabinet_url
                        player.pod_ready = True
                        print(f"✅ Cabinet ready for {player.username}")
                        return True
                        
            except Exception as e:
                print(f"⏳ Waiting for {player.username} cabinet: {str(e)[:50]}...")
            
            await asyncio.sleep(10)
        
        print(f"❌ Cabinet timeout for {player.username}")
        return False
    
    async def load_home_page(self, session: aiohttp.ClientSession, player: Player) -> bool:
        """Load home page and check game states"""
        try:
            async with session.get(f"{player.cabinet_url}/home") as response:
                player.requests_made += 1
                if response.status == 200:
                    player.pages_loaded += 1
                    html_content = await response.text()
                    
                    # Check current game states from the progression API  
                    await self.update_player_progression(session, player)
                    
                    print(f"🏠 {player.username}: Loaded home page, unlocked games: {player.unlocked_games}")
                    return True
                else:
                    player.errors += 1
                    player.error_details.append(f"home_page: {response.status}")
                    return False
                    
        except Exception as e:
            player.errors += 1
            player.error_details.append(f"home_page_error: {str(e)[:30]}")
            return False
    
    async def update_player_progression(self, session: aiohttp.ClientSession, player: Player):
        """Update player's progression state from API"""
        try:
            async with session.get(f"{player.cabinet_url}/progression") as response:
                player.requests_made += 1
                if response.status == 200:
                    progression_data = await response.json()
                    level_state = progression_data.get("level_state", {})
                    
                    # Update unlocked games list
                    player.unlocked_games = [game for game, state in level_state.items() 
                                           if state == "unlocked"]
                    
                else:
                    player.errors += 1
                    player.error_details.append(f"progression: {response.status}")
                    
        except Exception as e:
            player.errors += 1
            player.error_details.append(f"progression_error: {str(e)[:30]}")
    
    async def select_and_play_game(self, session: aiohttp.ClientSession, player: Player, 
                                 game_name: str) -> bool:
        """Select a game and simulate playing it"""
        try:
            # Step 1: Navigate to game (POST to /game route)
            game_data = {
                'title': game_name,
                'description': f'Playing {game_name}',
                'uri': f'{game_name}.html'
            }
            
            async with session.post(f"{player.cabinet_url}/game", data=game_data) as response:
                player.requests_made += 1
                if response.status == 200:
                    player.pages_loaded += 1
                    print(f"🎮 {player.username}: Loaded {game_name} game page")
                    
                    # Step 2: Simulate actual gameplay
                    await self.simulate_game_session(session, player, game_name)
                    return True
                else:
                    player.errors += 1
                    player.error_details.append(f"game_load_{game_name}: {response.status}")
                    return False
                    
        except Exception as e:
            player.errors += 1
            player.error_details.append(f"game_select_error: {str(e)[:30]}")
            return False
    
    async def simulate_game_session(self, session: aiohttp.ClientSession, player: Player, 
                                  game_name: str):
        """Simulate playing a game with realistic timing and score submission"""
        
        # Simulate game loading time
        await asyncio.sleep(random.uniform(2, 5))
        
        # Generate realistic game session data based on game type
        game_duration = random.randint(30, 120)  # 30-120 seconds gameplay
        
        if game_name == "imvaders":
            score_data = {
                "game_session_id": f"session-{player.username}-{int(time.time())}",
                "title": "imvaders",
                "player_name": player.username,
                "version": "1.0",
                "current_score": random.randint(500, 3000),
                "projectiles": random.randint(50, 200),
                "duration": game_duration
            }
        elif game_name == "logger":
            score_data = {
                "game_session_id": f"session-{player.username}-{int(time.time())}",
                "title": "logger", 
                "player_name": player.username,
                "version": "1.5",
                "current_score": random.randint(1000, 5000),
                "level": random.randint(1, 5),
                "movement": random.randint(100, 500),
                "duration": game_duration
            }
        else:
            # Generic game data
            score_data = {
                "game_session_id": f"session-{player.username}-{int(time.time())}",
                "title": game_name,
                "player_name": player.username,
                "version": "1.0",
                "current_score": random.randint(500, 2500),
                "duration": game_duration
            }
        
        # Simulate gameplay duration
        print(f"🕹️  {player.username}: Playing {game_name} for {game_duration}s...")
        await asyncio.sleep(min(game_duration / 10, 10))  # Scale down for load test
        
        # Submit game score
        try:
            async with session.post(f"{player.cabinet_url}/record_game_score/", 
                                  json=score_data) as response:
                player.requests_made += 1
                if response.status == 200:
                    player.games_played += 1
                    if game_name not in player.games_completed:
                        player.games_completed.append(game_name)
                    print(f"📊 {player.username}: Completed {game_name} (score: {score_data['current_score']})")
                else:
                    player.errors += 1
                    player.error_details.append(f"score_submit_{game_name}: {response.status}")
                    
        except Exception as e:
            player.errors += 1
            player.error_details.append(f"score_error: {str(e)[:30]}")
    
    async def answer_single_quiz_question(self, session: aiohttp.ClientSession, player: Player, 
                                        game_name: str, question_num: int) -> bool:
        """Answer a single quiz question (for parallel processing)"""
        try:
            # Step 1: Get quiz question
            async with session.get(f"{player.cabinet_url}/questions?module={game_name}&question_count=1") as response:
                player.requests_made += 1
                if response.status != 200:
                    player.errors += 1
                    player.error_details.append(f"quiz_load_{game_name}: {response.status}")
                    return False
                
                player.pages_loaded += 1
                html_content = await response.text()
                
                # Extract CSRF token for quiz submission
                csrf_token = self.extract_csrf_token(html_content)
                
            # Step 2: Submit quiz answer (simulate correct answer)
            quiz_data = {
                "player_name": player.username,
                "title": game_name,
                "question": f"Sample {game_name} question {question_num}",
                "attempts": 1,
                "time_taken": random.uniform(5, 30),
                "source": "static"
            }
            if csrf_token:
                quiz_data['csrf_token'] = csrf_token
            
            async with session.post(f"{player.cabinet_url}/answer", 
                                  json=quiz_data) as response:
                player.requests_made += 1
                if response.status == 200:
                    player.quiz_questions_answered[game_name] += 1
                    print(f"✅ {player.username}: Answered question {question_num} for {game_name}")
                    return True
                else:
                    player.errors += 1
                    player.error_details.append(f"quiz_answer_{game_name}: {response.status}")
                    return False
            
        except Exception as e:
            player.errors += 1
            player.error_details.append(f"quiz_error: {str(e)[:30]}")
            return False

    async def answer_quiz_questions(self, session: aiohttp.ClientSession, player: Player, 
                                  game_name: str) -> bool:
        """Answer quiz questions to unlock next game"""
        if game_name not in self.quiz_requirements:
            return True
            
        questions_needed = self.quiz_requirements[game_name]
        
        print(f"📝 {player.username}: Answering {questions_needed} quiz questions for {game_name}")
        
        concurrent_questions = min(3, questions_needed)
        questions_answered = 0
        
        for batch_start in range(0, questions_needed, concurrent_questions):
            batch_size = min(concurrent_questions, questions_needed - batch_start)
            
            question_tasks = []
            for i in range(batch_size):
                question_num = batch_start + i + 1
                task = asyncio.create_task(
                    self.answer_single_quiz_question(session, player, game_name, question_num)
                )
                question_tasks.append(task)
            
            batch_results = await asyncio.gather(*question_tasks, return_exceptions=True)
            questions_answered += sum(1 for result in batch_results if result is True)
            
            if batch_start + batch_size < questions_needed:
                await asyncio.sleep(random.uniform(1, 3))
        
        if questions_answered >= questions_needed:
            player.quizzes_completed += 1
            print(f"🎓 {player.username}: Completed all {questions_answered} quiz questions for {game_name}")
            return True
        else:
            print(f"❌ {player.username}: Only answered {questions_answered}/{questions_needed} questions for {game_name}")
            return False
    
    async def simulate_staggered_user_journey(self, session: aiohttp.ClientSession, 
                                            player: Player, duration: int, start_delay: float):
        """Simulate user journey with staggered start"""
        
        if not player.cabinet_url:
            print(f"❌ {player.username}: No cabinet URL available")
            return
        
        if start_delay > 0:
            print(f"⏰ {player.username}: Waiting {start_delay:.1f}s before starting journey")
            await asyncio.sleep(start_delay)
        
        print(f"🚀 {player.username}: Starting complete user journey for {duration}s")
        start_time = time.time()
        
        if not await self.load_home_page(session, player):
            return
        
        concurrent_tasks = []
        
        while time.time() - start_time < duration:
            try:
                progression_task = asyncio.create_task(self.update_player_progression(session, player))
                await progression_task
                
                available_games = [game for game in player.unlocked_games 
                                 if game in self.game_sequence]
                
                if not available_games:
                    print(f"🎉 {player.username}: No more games to unlock!")
                    break
                
                unplayed_games = [game for game in available_games 
                                if game not in player.games_completed]
                
                if unplayed_games:
                    current_game = random.choice(unplayed_games)
                else:
                    current_game = random.choice(available_games)
                
                print(f"🎯 {player.username}: Selected {current_game}")
                
                game_task = asyncio.create_task(self.select_and_play_game(session, player, current_game))
                
                if await game_task:
                    if current_game in self.quiz_requirements:
                        quiz_task = asyncio.create_task(
                            self.answer_quiz_questions(session, player, current_game)
                        )
                        
                        quiz_success = await quiz_task
                        
                        if quiz_success:
                            await self.update_player_progression(session, player)
                
                pause_duration = random.uniform(2, 8)
                await asyncio.sleep(pause_duration)
                
            except Exception as e:
                player.errors += 1
                player.error_details.append(f"journey_error: {str(e)[:30]}")
                print(f"⚠️  {player.username}: Journey error - {e}")
        
        if concurrent_tasks:
            await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        # Final summary
        error_rate = (player.errors / player.requests_made * 100) if player.requests_made > 0 else 0
        print(f"🏁 {player.username} journey complete:")
        print(f"   📊 {player.requests_made} requests, {player.errors} errors ({error_rate:.1f}%)")
        print(f"   📄 {player.pages_loaded} pages loaded")
        print(f"   🎮 {player.games_played} games played: {', '.join(player.games_completed)}")
        print(f"   📝 {player.quizzes_completed} quizzes completed")
        print(f"   🔓 {len(player.unlocked_games)} games unlocked: {', '.join(player.unlocked_games)}")
        
        if player.errors > 0:
            print(f"   ❌ Top errors: {', '.join(player.error_details[:3])}")

    async def simulate_complete_user_journey(self, session: aiohttp.ClientSession, 
                                           player: Player, duration: int):
        """Legacy method - redirects to staggered version with no delay"""
        await self.simulate_staggered_user_journey(session, player, duration, 0)
    
    async def cleanup_player_pods(self):
        """Clean up all created player pods (local environment only)"""
        if not self.created_users:
            return
            
        if self.production:
            print(f"\n🏭 Production mode: Skipping pod cleanup for {len(self.created_users)} users")
            print("   (Production pods managed by external systems)")
            return
            
        print(f"\n🧹 Cleaning up {len(self.created_users)} player pods...")
        
        try:
            from kubernetes import client, config
            
            try:
                config.load_incluster_config()
            except:
                config.load_kube_config()
            
            apps_v1 = client.AppsV1Api()
            core_v1 = client.CoreV1Api()
            
            cleanup_success = 0
            for username in self.created_users:
                try:
                    deployment_name = f"splunk-arcade-player-{username}"
                    service_name = f"splunk-arcade-cabinet-player-{username}"
                    
                    apps_v1.delete_namespaced_deployment(name=deployment_name, namespace="splunk-arcade")
                    core_v1.delete_namespaced_service(name=service_name, namespace="splunk-arcade")
                    
                    cleanup_success += 1
                    print(f"🗑️  Deleted pod for {username}")
                    
                except Exception as e:
                    print(f"⚠️  Failed to cleanup {username}: {e}")
            
            print(f"✅ Cleaned up {cleanup_success}/{len(self.created_users)} pods")
                   
        except ImportError:
            print("⚠️  Kubernetes client not available for cleanup")
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    async def run_e2e_test(self, num_users: int, duration: int = 180, burst_mode: bool = False,
                         reg_batch_size: int = 15, login_batch_size: int = 20):
        """Run complete E2E user test with full game progression"""
        
        print(f"🚀 Starting End2End USER load test")
        print(f"👥 Users: {num_users}")
        print(f"🌐 Portal: {self.portal_url}")
        print(f"🔒 Production mode: {self.production} (SSL validation: {'disabled' if self.production else 'enabled'})")
        print(f"⏱️  Journey duration: {duration}s per user")
        print(f"⚡ Burst mode: {burst_mode} (staggered starts: {not burst_mode})")
        print(f"🔄 Batch sizes - Registration: {reg_batch_size}, Login: {login_batch_size}")
        print(f"🎮 Games in sequence: {' → '.join(self.game_sequence)}")
        
        # Connection settings optimized for full page loads
        ssl_context = None
        if self.production:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=15,
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True,
            ssl=ssl_context
        )
        timeout = aiohttp.ClientTimeout(total=45, connect=15)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            try:
                # Phase 1: Registration
                print(f"\n👤 Phase 1: Registering {num_users} users...")
                all_players = []
                for i in range(num_users):
                    username = self.generate_valid_username(i)
                    password = f"password{i:03d}"
                    all_players.append(Player(username=username, password=password, session_cookies={}))
                
                batch_size = min(reg_batch_size, num_users)
                
                for i in range(0, len(all_players), batch_size):
                    batch = all_players[i:i + batch_size]
                    print(f"   Registering batch {i//batch_size + 1}/{(len(all_players) + batch_size - 1)//batch_size}...")
                    
                    reg_tasks = [asyncio.create_task(
                        self.register_user(session, player.username, player.password)
                    ) for player in batch]
                    
                    reg_results = await asyncio.gather(*reg_tasks, return_exceptions=True)
                    
                    for player, success in zip(batch, reg_results):
                        if success is True:
                            self.players.append(player)
                    
                    if i + batch_size < len(all_players):
                        await asyncio.sleep(0.5)
                
                if not self.players:
                    print("❌ No users registered successfully")
                    return
                
                print(f"✅ Registered {len(self.players)} out of {num_users} users")
                
                # Phase 2: Login
                print(f"\n🔐 Phase 2: Logging in {len(self.players)} users...")
                
                batch_size = min(login_batch_size, len(self.players))
                logged_in_players = []
                
                for i in range(0, len(self.players), batch_size):
                    batch = self.players[i:i + batch_size]
                    print(f"   Logging in batch {i//batch_size + 1}/{(len(self.players) + batch_size - 1)//batch_size}...")
                    
                    login_tasks = [asyncio.create_task(self.login_user(session, player)) for player in batch]
                    login_results = await asyncio.gather(*login_tasks, return_exceptions=True)
                    
                    batch_logged_in = [p for p, success in zip(batch, login_results) if success]
                    logged_in_players.extend(batch_logged_in)
                    
                    if i + batch_size < len(self.players):
                        await asyncio.sleep(1)
                
                print(f"✅ Logged in {len(logged_in_players)} out of {len(self.players)} users")
                
                # Phase 3: Wait for cabinet pods
                print(f"\n⏳ Phase 3: Waiting for {len(logged_in_players)} cabinet pods...")
                
                cabinet_tasks = [asyncio.create_task(self.wait_for_cabinet_ready(session, player)) 
                               for player in logged_in_players]
                
                batch_size = 6
                cabinet_results = []
                
                for i in range(0, len(cabinet_tasks), batch_size):
                    batch_tasks = cabinet_tasks[i:i + batch_size]
                    print(f"   Checking cabinet batch {i//batch_size + 1}/{(len(cabinet_tasks) + batch_size - 1)//batch_size}...")
                    
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    cabinet_results.extend(batch_results)
                    
                    if i + batch_size < len(cabinet_tasks):
                        await asyncio.sleep(5)
                
                ready_players = [p for p, ready in zip(logged_in_players, cabinet_results) if ready]
                
                if not ready_players:
                    print("❌ No player cabinets became ready")
                    return
                
                print(f"✅ {len(ready_players)} cabinet pods ready")
                
                # Phase 4: User journeys
                print(f"\n🎮 Phase 4: Running complete user journeys...")
                
                journey_tasks = []
                
                if burst_mode:
                    print(f"   ⚡ Burst mode: All {len(ready_players)} users starting immediately")
                    for player in ready_players:
                        task = asyncio.create_task(
                            self.simulate_staggered_user_journey(session, player, duration, 0)
                        )
                        journey_tasks.append(task)
                else:
                    stagger_window = min(60, duration // 3)
                    print(f"   📈 Staggering user starts over {stagger_window:.1f}s")
                    
                    for i, player in enumerate(ready_players):
                        start_delay = random.uniform(0, stagger_window) if len(ready_players) > 1 else 0
                        
                        task = asyncio.create_task(
                            self.simulate_staggered_user_journey(session, player, duration, start_delay)
                        )
                        journey_tasks.append(task)
                
                await asyncio.gather(*journey_tasks, return_exceptions=True)
                
                # Phase 5: Final results
                print(f"\n📊 End2End TEST RESULTS:")
                
                total_requests = sum(p.requests_made for p in ready_players)
                total_errors = sum(p.errors for p in ready_players)
                total_pages = sum(p.pages_loaded for p in ready_players)
                total_games = sum(p.games_played for p in ready_players)
                total_quizzes = sum(p.quizzes_completed for p in ready_players)
                
                overall_error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
                
                print(f"   👥 Users tested: {len(ready_players)}")
                print(f"   📄 Total pages loaded: {total_pages}")
                print(f"   🎮 Total games played: {total_games}")
                print(f"   📝 Total quizzes completed: {total_quizzes}")
                print(f"   🌐 Total requests: {total_requests}")
                print(f"   ❌ Total errors: {total_errors}")
                print(f"   📊 Overall error rate: {overall_error_rate:.2f}%")
                print(f"   ⚡ Requests/second: {total_requests / duration:.2f}")
                
                # Show progression achievements
                games_unlocked = {}
                for player in ready_players:
                    for game in player.unlocked_games:
                        games_unlocked[game] = games_unlocked.get(game, 0) + 1
                
                print(f"\n🎯 PROGRESSION ACHIEVEMENTS:")
                for game in self.game_sequence:
                    count = games_unlocked.get(game, 0)
                    percentage = (count / len(ready_players) * 100) if ready_players else 0
                    print(f"   {game}: {count}/{len(ready_players)} users unlocked ({percentage:.1f}%)")
                
                # Assessment
                print(f"\n🎯 REALISTIC USER ASSESSMENT:")
                if overall_error_rate > 15.0:
                    print(f"❌ CRITICAL: System cannot handle realistic user load")
                elif overall_error_rate > 10.0:
                    print(f"⚠️  HIGH ERROR RATE: Significant issues with full user journeys")
                elif overall_error_rate > 5.0:
                    print(f"⚠️  MODERATE ERRORS: Some issues with page loads or navigation")
                elif total_games < len(ready_players):
                    print(f"⚠️  LIMITED GAMEPLAY: Users unable to progress through games")
                else:
                    print(f"✅ EXCELLENT: System handles realistic user journeys well")
                    
            except Exception as e:
                print(f"❌ Test failed with error: {e}")
                raise
            finally:
                await self.cleanup_player_pods()


async def main():
    parser = argparse.ArgumentParser(description="End2End User Journey Load Tester")
    parser.add_argument("--portal-url", default=None,
                       help="Portal URL (default: auto-detected based on --production flag)")
    parser.add_argument("--users", type=int, default=5,
                       help="Number of concurrent users (default: 5)")
    parser.add_argument("--duration", type=int, default=180,
                       help="User journey duration per user in seconds (default: 180)")
    parser.add_argument("--production", action="store_true",
                       help="Use production HTTPS URL and ignore SSL validation (default: local HTTP)")
    parser.add_argument("--burst", action="store_true",
                       help="All users start immediately (no staggered starts for burst testing)")
    parser.add_argument("--reg-batch-size", type=int, default=15,
                       help="Registration batch size for parallel processing (default: 15)")
    parser.add_argument("--login-batch-size", type=int, default=20,
                       help="Login batch size for parallel processing (default: 20)")
    
    args = parser.parse_args()
    
    # Set default portal URL based on production flag
    if args.portal_url is None:
        if args.production:
            portal_url = "https://us.splunkarcade.com"
        else:
            portal_url = "http://splunk-arcade.home:80"
    else:
        portal_url = args.portal_url
    
    tester = End2EndUserTester(portal_url, production=args.production)
    await tester.run_e2e_test(
        num_users=args.users, 
        duration=args.duration,
        burst_mode=args.burst,
        reg_batch_size=args.reg_batch_size,
        login_batch_size=args.login_batch_size
    )


if __name__ == "__main__":
    asyncio.run(main())
