# Splunk Arcade Load Testing Suite

Load tests for local testing (Thanks in large part to El Elem)

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
```

## Expected Results

### End2End Test
- **Frontend + Backend**: Tests complete user experience end-to-end
- **Expected capacity**: 3-8 users (more resource intensive)
- **Progression tracking**: Shows game unlock rates and quiz completion
- **Page load performance**: Tests HTML rendering and navigation


## Features

- **Automatic pod cleanup**: All tests clean up after completion
- **Detailed progression tracking**: Shows game unlock progression and quiz completion  
- **Real user workflow**: Follows actual game unlock sequence
- **Performance metrics**: Page loads, games played, quizzes completed
- **Error categorization**: Specific failure types per user and endpoint
