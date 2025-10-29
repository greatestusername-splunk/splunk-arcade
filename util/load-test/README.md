# Splunk Arcade Load Testing Suite

Load tests for local (and --production) testing (With special thanks to El Elem)

## 1. End2End User Test

**Complete user journey simulation including page loads, game progression, and quiz answering.**

```bash
# Install dependencies  
source venv/bin/activate
cd util/load-test 
pip install -r requirements.txt

# Test complete user journeys
python e2e_user_test.py --users 5 --duration 180
```



## What Each Test Does

### End2End User Test
**COMPLETE user experience simulation that spins up testing pods:**
1. **Registration & Login** → Portal user creation & authentication
2. **Home Page Navigation** → Loads actual HTML pages  
3. **Game Selection & Loading** → Navigates to game pages
4. **Actual Gameplay Simulation** → Plays games with realistic timing
5. **Quiz Question Answering** → Answers questions to unlock progression
6. **Game Progression Flow** → Unlocks games in proper sequence (imvaders → logger → bughunt → etc.)
7. **Multi-Game Navigation** → Follows real user workflow


## Usage

```bash
# End2End user journeys (tests everything)
python e2e_user_test.py --users 3 --duration 120
python e2e_user_test.py --users 50 --duration 300

# Production testing (HTTPS + ignore SSL validation)
python e2e_user_test.py --production --users 5 --duration 180
python e2e_user_test.py --production --portal-url https://custom.domain.com --users 10

# High concurrency testing (optimized for load generation)
python e2e_user_test.py --users 50 --burst --reg-batch-size 25 --login-batch-size 30
python e2e_user_test.py --production --users 100 --duration 300 --reg-batch-size 30
```
**NOTE: When running against --production the script CANNOT clean up pods.**
- Clean up loadtest deployments on the cluster with  
 `kubectl get deployments --no-headers -o custom-columns=":metadata.name" | grep player-loadtest-user | while read deployment; do kubectl delete deployment "$deployment"; done`

## Expected Results

### End2End Test
- **Frontend + Backend**: Tests complete user experience end-to-end
- **Expected capacity**: 3-100+ users (Based on cluster resources and concurrency settings)
- **Progression tracking**: Shows game unlock rates and quiz completion
- **Page load performance**: Tests HTML rendering and navigation
- **Concurrent load generation**: Multiple parallel operations per user + staggered starts


## Features

- **Automatic pod cleanup**: All tests clean up after completion
- **Detailed progression tracking**: Shows game unlock progression and quiz completion  
- **Real user workflow**: Follows actual game unlock sequence
- **Performance metrics**: Page loads, games played, quizzes completed
- **Error categorization**: Specific failure types per user and endpoint
- **Production testing**: `--production` flag for HTTPS testing with SSL bypass (skips pod cleanup)
- **High concurrency**: Parallel registration/login batches + concurrent quiz answering
- **Load patterns**: Staggered user starts (default) or `--burst` mode for spike testing
- **Configurable batching**: `--reg-batch-size` and `--login-batch-size` for tuning throughput

## Concurrency Optimizations

**Parallel Operations:**
- Registration: Batched parallel requests (15-30 per batch)  
- Login: Batched parallel authentication (20-30 per batch)
- Quiz answering: Up to 3 questions answered simultaneously per user
- User journeys: Concurrent game sessions + progression checks

**Load Patterns:**
- **Staggered (default)**: Users start over 60s window for realistic traffic
- **Burst mode**: All users start immediately for spike testing (`--burst`)

**Timing Improvements:**
- Removed 1.5s delays between registrations (now 0.5s between batches)
- Reduced login delays from 3s to 1s between batches  
- Shortened user navigation pauses from 5-15s to 2-8s
