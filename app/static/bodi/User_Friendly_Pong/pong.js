var canvas = document.getElementById("canvas");
var screenWidth = window.innerWidth;
var screenHeight = window.innerHeight;
canvas.width = screenWidth;
canvas.height = screenHeight;
var context = canvas.getContext("2d");
var playing = false;
var ingame1 = false;
var wait = 0;
var times = 1;
var done = false;
var win = false;
var lose = false;
var classicmode = document.getElementById("ClassicMode");
classicmode.style.left = screenWidth/6.75 + 'px';
classicmode.style.top = screenHeight/3 + 'px';
classicmode.style.width = screenWidth/8 + 'px';
classicmode.style.height = screenWidth/8 + 'px';
var CMI = document.getElementById("CMI");
CMI.style.left = screenWidth/6.75 + 'px';
CMI.style.top = screenHeight/1.5 + 'px';
CMI.style.width = screenWidth/8 + 'px';
CMI.style.height = screenWidth/8 + 'px';
var instructions1 = false;   
var home = document.getElementById("Home");
var startOver = document.getElementById("StartOver");
startOver.style.left = screenWidth/2 - 242 + 'px';
startOver.style.top = screenHeight/2 - 50 + 'px';
startOver.style.width = 500 + 'px';
startOver.style.height = 100 + 'px';

var goingUp = false;
var goingDown = false;
var paddle = {
    x: screenWidth/2 - 225,
    y: screenHeight/2 - 25,
    width: 9,
    height: 75
};

var enemyPaddle = {
    x: screenWidth/2 + 225,
    y: screenHeight/2 - 25,
    width: 9,
    height: 75
};

var ball = {
    x: screenWidth/2,
    y: screenHeight/2 + 200,
    rad: 5,
    dx: 2.5,
    dy: -2.5
}



function hideStuff() {
    playing = true;
    classicmode.style.display = "none";
    CMI.style.display = "none";
}

function classicInstructions() {
    if(instructions1 === true) {
    context.font = "50px Arial";
    context.fillText("Instructions:", screenWidth/2 - screenWidth/10, screenHeight/8);
    context.font = "25px Arial";
    context.fillText("- Single Player Game", screenWidth/4 - screenWidth/10, screenHeight/5);
    context.fillText('- Use "W" and "S" keys to move your paddle up and down', screenWidth/4 - screenWidth/10, screenHeight/4);
    context.fillText("- Try to hit the ball with your paddle", screenWidth/4 - screenWidth/10, screenHeight/3.35);
    context.fillText("- If you fail to deflect it, and the ball hits your side, you lose", screenWidth/4 - screenWidth/10, screenHeight/2.85);
    context.fillText("- The ball speeds up as the game goes on", screenWidth/4 - screenWidth/10, screenHeight/2.50);
    context.fillText("- You win if the ball hits your opponent's side", screenWidth/4 - screenWidth/10, screenHeight/2.2);
    }
}

function classicGame() {
    if(ingame1 === true) {
        function gameBasics() {
            context.strokeStyle = "black";
            context.strokeRect(screenWidth/2 - 250, screenHeight/2 - 250, 500, 500);
            context.fillStyle = "white";
            context.fillRect(screenWidth/2 - 250, screenHeight/2 - 250, 500, 500);
        }
        
        function drawPaddle() {
            context.fillStyle = "blue";
            context.fillRect(paddle.x, paddle.y, paddle.width, paddle.height);
        }
        
        function movePaddle() {
            if(goingDown && paddle.y < screenHeight/2 + 250 - paddle.height) {
                paddle.y+=5;
            }
            if(goingUp && paddle.y > screenHeight/2 - 250) {
                paddle.y-=5;
            }
        }
        
        function drawEnemyPaddle() {
            context.fillStyle = "red";
            context.fillRect(enemyPaddle.x, enemyPaddle.y, enemyPaddle.width, enemyPaddle.height);
        }
        
        function moveEnemyPaddle() {
            if(enemyPaddle.y + 75/2 > ball.y && enemyPaddle.y > screenHeight/2 - 248) {
                enemyPaddle.y -= 4;
            }
            if(enemyPaddle.y + 75/2 < ball.y && enemyPaddle.y + 75 < screenHeight/2 + 250) {
                enemyPaddle.y += 4;
            }
        }
        
        function drawBall() {
            context.beginPath();
            context.arc(ball.x, ball.y, ball.rad, 0, 360);
            context.fillStyle = "green";
            context.fill();
            context.closePath();
        }
        
        function moveBall() {
            ball.x += ball.dx;
            ball.y -= ball.dy;
        }
        
        function checkBallCollision() {
            if(paddle.x < ball.x && paddle.x + paddle.width * 1.5 > ball.x && paddle.y < ball.y && paddle.y + paddle.height > ball.y) {
                ball.dx = -(ball.dx);
                ball.x += ball.dx * 2;
                speedBallUp();
            }
            if(enemyPaddle.x < ball.x && enemyPaddle.x + enemyPaddle.width * 1.5 > ball.x && enemyPaddle.y < ball.y && enemyPaddle.y + enemyPaddle.height > ball.y ) {
                ball.dx = -(ball.dx);
                ball.x += ball.dx * 2;
                speedBallUp();
                ball.dy = -(ball.dy);
            }
            if(ball.y >= screenHeight/2 + 250)  {
                ball.dy = -(ball.dy);
            }
            if(ball.y <= screenHeight/2 - 250) {
                ball.dy = -(ball.dy);
            }
            if(ball.x < screenWidth/2 - 249) {
                startOver.style.display = "inline";
                lose = true;
                done = true;
            }
            if(ball.x > screenWidth/2 + 249) {
                startOver.style.display = "inline";
                win = true;
                done = true;
            }
            
        }
        
        function speedBallUp() {
            if(ball.dx > 0) {
                ball.dx += 0.25;
            } else {
                ball.dx -= 0.25;
            }
            ball.dy = (ball.dy/Math.abs(ball.dy)) * (Math.random() * ball.dx * 0.5);
        }
        
        function classicUpdate() {
            context.clearRect(screenWidth/2 - 250, screenHeight/2 - 250, 500, 500);
            gameBasics();
            drawPaddle();
            movePaddle();
            drawEnemyPaddle();
            moveEnemyPaddle();
            drawBall();
            moveBall();
            checkBallCollision();
            setTimeout(classicUpdate, 5000*times);
            if(done === true) {
                ingame1 = false;
            }
            times++;
        }
        
        if(wait > 0) {
                context.fillStyle = "rgb(255, 255, 255)";
                context.fillRect(screenWidth/2 - 50, screenHeight/2 - 50, 100, 100);
                context.fillStyle = "rgb(0, 0, 0)";
                context.font = "50px Arial";
                context.fillText(wait, screenWidth/2 - 15, screenHeight/2 + 20);
        } else {
            classicUpdate();
        }
        
        window.addEventListener("keydown", keyDown);
        window.addEventListener("keyup", keyUp);
        
        function keyDown(event) {
            switch(event.keyCode) {
                case 87:
                    goingUp = true;
                    break;
                case 83:
                    goingDown = true;
                    break;
                default:
            }
        }
        
        function keyUp(event) {
            switch(event.keyCode) {
                case 87:
                    goingUp = false;
                    break;
                case 83:
                    goingDown = false;
                    break;
                default:
            }
        }
    }
}

var image = new Image();
image.src = 'images/title.png';

function displayTitle() {
    if(playing === false) {
        context.drawImage(image, screenWidth/8, screenHeight/64, screenWidth * 3/4, screenHeight/4);
    }
}

function update() {
    context.clearRect(0, 0, screenWidth, screenHeight);
    displayTitle();
    classicInstructions();
    classicGame();
    if(lose) {
        context.font = "100px Arial";
        context.fillStyle = "black";
        context.fillText("You Lose", screenWidth/2 - screenWidth/8 + screen.width/24, screenHeight/2 - 250);
    }
    if(win) {
        context.font = "100px Arial";
        context.fillStyle = "black";
        context.fillText("You Win", screenWidth/2 - screenWidth/8 + screen.width/20, screenHeight/2 - 250);
    }
    setTimeout(update, 15);
}

update();

//classicmode.addEventListener("click", function() {
//    alert("We are sorry, but this game mode is not currently available.");
//});

classicmode.addEventListener("click", function() {
    hideStuff();
    classicGame();
    ingame1 = true;
    wait = 3;
    setTimeout(function() {wait--;}, 1000);
    setTimeout(function() {wait--;}, 2000);
    setTimeout(function() {wait--;}, 3000);
    document.body.style.background = "rgb(105, 105, 105)";
});

CMI.addEventListener("click", function() {
    hideStuff();
    instructions1 = true;
});

home.addEventListener("click", function() {
    window.location.reload();
});

startOver.addEventListener("click", function() {
    hideStuff();
    classicGame();
    win = false;
    lose = false;
    ingame1 = true;
    wait = 3;
    done = false;
    setTimeout(function() {wait--;}, 1000);
    setTimeout(function() {wait--;}, 2000);
    setTimeout(function() {wait--;}, 3000);
    document.body.style.background = "rgb(105, 105, 105)";
    
    goingUp = false;
    goingDown = false;
    paddle = {
    x: screenWidth/2 - 225,
    y: screenHeight/2 - 25,
    width: 9,
    height: 75
};
    
    enemyPaddle = {
        x: screenWidth/2 + 225,
        y: screenHeight/2 - 25,
        width: 9,
        height: 75
    };
    
    ball = {
        x: screenWidth/2,
        y: screenHeight/2 + 200,
        rad: 5,
        dx: 2.5,
        dy: -2.5
    }
    startOver.style.display = "none";
});