// opacity
// green tank that shoots

// enemies that shoot at you

// metalboss
	// always charge player
	// move faster than the player

// collision stuff
// healthbar
// powerups/new ammo

var isacMode = false;

var isacCount = 0;

var cooperMode = false;

var roboFreeze = false;

var ghost = false;

var imortal = false;

var kazuyaMode = false;

var kazuyaCheat = 0;

var laserUpgrade = false;

var coinAmount = 0;

var metalAmount = 0;

var healthBoosts = 0;

var cheat = 0;

var enemies = [];

var activeWeapon = null;
var equipment = {
	laser: false,
	telegun: false,
};

var powerShots = 0;

var score = 0;

var gamecan = document.getElementById("gamecan");
gamecan.width = document.body.offsetWidth;
gamecan.height = document.body.offsetHeight;

window.addEventListener("keydown", keyDown);

var tools = gamecan.getContext("2d");

var gameObjects = [];
var beamParticles = [];

function randomEnemy() {
    var range = 5000;

	var enemyX = player.position.x + (Math.random() * range * 2) - range;

	if (enemyX < 0) {
		enemyX = 0;
	}

	var type;
	var image;
	if (Math.random() * 20 > 19 && score >= 50) {
		image = 'images/aw_rad.gif';
		type = 'heavy';
	} else {
		image = 'images/metalboss.gif';
		type = 'metalboss';
    }

    new Enemy(enemyX, -100, 50, 50, type, image);
}

function fort() {
	var fortWall = new GameObject(player.position.x - 200, player.position.y + 800, 25, 200);
	fortWall.tags.push("fortWall");

	var fortWall = new GameObject(player.position.x + 200, player.position.y + 900, 25, 200);
	fortWall.tags.push("fortWall");

	var fortWall = new GameObject(player.position.x - 200, player.position.y + 1000, 425, 25);
	fortWall.tags.push("fortRoof");
}

function nuke() {
	var nuke = new GameObject(player.position.x, player.position.y + 500, 100, 100, "images/nuke.png");
	nuke.tags.push('nuke');
}

function Character(x,y,w,h,image) {
    GameObject.call(this, x, y, w, h, image);

	var me = this;
	
	me.maxHealth = 100;
	me.health = me.maxHealth;
    me.speed = 4;
    me.tags.push('character');

	me.changeHealth = function(amount) {
		me.health += amount;
	    me.opacity = me.health / me.maxHealth;

		if(me.health <= 0) {
			me.defeat();
		}
	}

	me.defeat = function() {
		me.destroy();

		if(me.tags.indexOf('enemy') != -1) {
			randomEnemy();
			
			
			var random = Math.floor(Math.random() * 5);
			
			console.log(random);
			

			if( random == 2 || me.type == 'heavy') {
				var coin = new GameObject(me.position.x,me.position.y,15,15,"images/coin.png");
				coin.tags.push("coin");
				
				
				
			} else if( random == 3) {
				
				var metal = new GameObject(me.position.x,me.position.y,15,15,"images/metal.png");
				metal.tags.push("metal");
			}
			
			

		    setTimeout(function() {
    		    randomEnemy();
		    }, 2000);


			if(player.health > 0) {
				score += me.value;
			}
		}
	}
}

function Enemy(x,y,w,h,type,image) {
	Character.call(this,x,y,w,h,image);
    var me = this;

    me.tags.push('enemy');

    enemies.push(me);

    me.value = 1;

    me.speed = 3;

    me.type = type;

    me.status = null;

    if(me.type == 'metalboss') {
    } else if(me.type == 'heavy') {
    	me.speed = 0.75;
    	me.health = 1000;
    	me.maxHealth = me.health;
    	me.value = 2;
    }

	me.think = function() {
    	if(me.type == 'metalboss' || me.type == 'heavy') {
			if (me.grounded == true && me.status != "blocked") {
				if (me.position.x > player.position.x) {
					me.position.x -= me.speed;
				} else{
					me.position.x += me.speed;

				}
			}
		}
	}
}

function GameObject(x,y,w,h,image) {
	var me = this;

	// this.x = x;
	// this.y = y;
	me.position = new Vector2D(x, y);
	me.velocity = new Vector2D(0, 0);
	me.w = w;
	me.h = h;
	me.static = false;
	me.kinematic = false;
	me.grounded = false;
	me.image = image;
	me.tags = [];
	me.opacity = 1;
	me.color = 'black';

	me.destroy = function() {
		gameObjects.splice(gameObjects.indexOf(me), 1);
		
		if(me.tags.indexOf('beamParticle') != -1) {
			beamParticles.splice(beamParticles.indexOf(me), 1);
		}

		if(me.tags.indexOf('enemy') != -1) {
			enemies.splice(enemies.indexOf(me), 1);
		}
	}

	gameObjects.push(this);
}

function Vector2D(x, y) {
	var me = this;
	me.x = x;
	me.y = y;

	me.add = function(anotherVector) {
		var newX = me.x + anotherVector.x;
		var newY = me.y + anotherVector.y;

		return new Vector2D(newX, newY);
	}

	me.subtract = function(anotherVector) {
		var newX = me.x - anotherVector.x;
		var newY = me.y - anotherVector.y;

		return new Vector2D(newX, newY);
	}

	me.getMagnitude = function() {
		var magnitude = Math.sqrt(me.x * me.x + me.y * me.y);
		return magnitude;
	}

	me.normalize = function() {
		var magnitude = me.getMagnitude();
		me.x /= magnitude;
		me.y /= magnitude;
	}

	me.scale = function(amount){
		me.x *= amount;
		me.y *= amount;
	}
}

var jumpBoosts = 0;
var xdirection = 0;
var metalboss = new Enemy(2000,0,50,50,'metalboss','images/metalboss.gif'); 
var player = new Character(0, 0, 100, 100);
var normalAcceleration = 0.5;
var maxSpeed = 4;

player.speed = normalAcceleration;

var underground = new GameObject(0, -1700, 10000000, 50);
underground.tags.push("underground");
underground.static = true;
var ground = new GameObject(0, -500, 10000000, 50);
ground.static = true;
// var cage = new GameObject(5000);


var bodiCount = 0;

//var range = 100;
var jumpBoost = new GameObject(Math.random() * 10000, -100, 20, 20, "images/jump.png");
jumpBoost.tags.push("jumpBoost");



var powerUp = new GameObject(Math.random() * 10500, -100, 30, 30, "images/powerUp.png");
powerUp.tags.push("powerUp");


var healthBoost = new GameObject(Math.random() * 10500, -100, 30, 30,"images/health.png");
healthBoost.tags.push("healthBoost");



// NEXT TIME!
function generateArea() {
    // generate stuff in like a 10000 unit area
}

function keyDown(event) {
	switch(event.keyCode) {
		case 87: {
			bodiCount ++;
			if(bodiCount > 3) {
				var bodiPassword = prompt("enter password");
				if(bodiPassword == "bodi") {
					alert("you are now imortal");
					imortal = true;
				}
			}
			
			function imortalfunk() {
			 
			imortal = true;
			
			
				
			}
			
			
			
			//w
			 // += 10;
		} break;

		case 83: { // s
			isacCount++;
			if(isacCount > 2) {
				var password2 = prompt("please enter your password");
				if (password2 == "isac") {
					isacMode = true;
				}
			}
		} break;
		
		case 52: {
			if(metalAmount > 9) {
				coinAmount += 5;
				metalAmount -= 10;
			} 
		} break;
		
		case 53: {
			if(coinAmount > 9) {
				coinAmount -= 10;
				metalAmount += 5;
			} break;
			
		 
			
		
		
		}
		
		case 73: {
			if (isacMode == true) {
			roboFreeze = true;
			}
		}

		case 65: {
			//a
			// player.x -= 5;
			xdirection = -1;
		} break;

		case 78: {
			if( cooperMode == true || metalAmount > 49) {	
			nuke();
			setTimeout(nuke, 100);
			setTimeout(nuke, 100);
			
			if( cooperMode == false) {
				metalAmount -= 50;
			}
			
		}  
			
		
		
		} break;

		case 68: {
			//d
			//player.x += 5;
			xdirection = 1;
		} break;

		case 32: {
			// spacebar
			if(jumpBoosts > 0 || cheat > 1) {
				player.grounded = false;
				player.position.y += 5;
				player.velocity.y = 4;
				maxSpeed = 10;
				jumpBoosts--;
			} else if(player.grounded ) {
				player.grounded = false;
				player.position.y += 5;
				player.velocity.y = 2;
			}
		} break;

		case 75: { // k
			kazuyaCheat +=1;
			
			if (kazuyaCheat > 2) {
				var password = prompt("password please");
				
				
				
				if (password == "cooper") {
					cooperMode = true;
					cheat = 2;
					alert("cooper mode activated");
				}
				if(password == "kazuya") {
					kazuyaMode = true;
					cheat = 2;
					alert("kazuya mode activated");
					
					
					
				} else {
					cheat = 0;
				}
			}
		} break;

		case 70: { // f
			if(kazuyaMode == true) {
			fort(); 
		}
		} break;

		case 16: {
			// SHIFT
			cheat++;
			if(cheat > 1) {
				maxSpeed = 10;
			}
		} break;
		
		case 38: { // up arrow
			ghost = true;
		} break;
		
		case 40: { // down arrow
			ghost = false;
		} break;
		
		case 79: { // o
			cheat--;
		} break;

		case 67: { // c
			if(cheat > 1) {
				coinAmount += 10;
				metalAmount += 10;
			}
		} break;

		case 49: { // 1
			activeWeapon = null;
		} break;

		case 50: { // 2
			if(!equipment.laser) {
				if(coinAmount >= 50) {
					equipment.laser = true;
					coinAmount -= 50;
				} else {
					return;
				}
			}

			activeWeapon = 'laser';
		} break;
		
		case 51: { // 3
			if (activeWeapon == 'laser' && coinAmount > 49) {
                if(laserUpgrade == false) {
				coinAmount -= 50;
				}
				laserUpgrade = true;
				
            }
			
		} break;

		case 81: {
			// Q
			if (healthBoosts > 0 || cheat > 1) {
				if(player.health > 0) {
					player.changeHealth(20);	
					healthBoosts--;
				} break;
			}
		} break;
	} 
}
    

window.addEventListener("keyup",keyUp)

function keyUp(event) {
	switch(event.keyCode) {
		case 65: {
			xdirection = 0;
		} break;

		case 68: {
			xdirection = 0;
		}break;

	}
}

function machinegun() {
	
}

function localToWorld(x, y) {
	y *= -1;
	x += (player.position.x - 500);
	y += (player.position.y + 500);

	return new Vector2D(x, y);
}


var mouseCoords = new Vector2D();
var attackVector = null;
var mousing = false;

window.addEventListener("mousedown", mouseDown);
window.addEventListener("mousemove", mouseMove);
window.addEventListener("mouseup", mouseUp);

function mouseDown(event) {
	var worldPosition = localToWorld(event.clientX, event.clientY);
	mouseCoords = worldPosition;

	mousing = true;

	if(activeWeapon == null) {
		if (powerShots > 0 || cheat > 1 || laserUpgrade == true) {
			if (kazuyaMode == false && isacMode == false) {
			var bullet = new GameObject(player.position.x + 70, player.position.y - 47, 20,10);
			bullet.tags.push('projectile');
			
			var bullet2 = new GameObject(player.position.x + 10, player.position.y - 47, 20,10);
			bullet2.tags.push('projectile');
			
			} else if(kazuyaMode == true) {
			bullet = new GameObject(player.position.x + 70, player.position.y - 47, 20,30, "images/kazuya.png");
			bullet.tags.push('projectile');	
			} if(isacMode == true) {
				
			bullet = new GameObject(player.position.x + 50, player.position.y - 47, 20,30, "images/banana.png");
			bullet.tags.push('projectile');	
			}
			
			
			
			
			
			var velocityVector = worldPosition.subtract(bullet.position);
			velocityVector.normalize();
			velocityVector.scale(50);
			bullet.velocity = velocityVector;
			bullet2.velocity = velocityVector;
			
		} else {
			
			bullet = new GameObject(player.position.x + 70, player.position.y - 47, 20,10);
			bullet.tags.push('projectile');
		
			var velocityVector = worldPosition.subtract(bullet.position);
			velocityVector.normalize();
		
			if (powerShots > 0 || cheat > 1) {
				velocityVector.scale(50);
			} else {
				velocityVector.scale(25);
			}

			bullet.velocity = velocityVector;
		}
	} else if(activeWeapon == 'laser') {
		var gunVector = player.position.add(new Vector2D(70, -47));
		var differenceVector = mouseCoords.subtract(gunVector);
		differenceVector.normalize();
		if(laserUpgrade == false) {
		differenceVector.scale(35);
		} else if(laserUpgrade == true) {
		differenceVector.scale(45);	
		}
		attackVector = differenceVector;
		
	}
	
}

function mouseMove(event) {
	var worldPosition = localToWorld(event.clientX, event.clientY);
	mouseCoords = worldPosition;
}

function mouseUp() {
	mousing = false;
	if(laserUpgrade == false) {
	for (var particleIndex = beamParticles.length - 1; particleIndex >= 0; particleIndex--) {
		var beamParticle = beamParticles[particleIndex];
		beamParticle.destroy();
	}
	}
}

var lastTime = new Date();
var timer = 0;

function update() {

	
	
	tools.clearRect(0,0,gamecan.width,gamecan.height);

	var currentTime = new Date();

	var timePassed = currentTime - lastTime;
	timer += timePassed;
	var secondsPassed = Math.floor(timePassed/1000);

	if(mousing == true && activeWeapon == 'laser') {
		if(laserUpgrade == false) {
		var beamParticle = new GameObject(player.position.x + 70, player.position.y - 47, 40, 40);
		beamParticle.color = 'red';
		} else {
		var beamParticle = new GameObject(player.position.x + 70, player.position.y - 47, 60, 40);
		beamParticle.color = 'green';	
		}
		beamParticle.tags.push("projectile");
		beamParticle.tags.push("beamParticle");
		beamParticle.kinematic = true;
		beamParticle.velocity = attackVector;
		
		beamParticles.push(beamParticle);
	}

	if(checkCollision(player, ground)) {
		player.grounded = true;
		player.velocity.y = 0;
	} else {
		player.grounded = false;
	}

	if(player.position.y < -10000) {
		player.position.y = 0;
		player.position.x = 0;
	}

	if(xdirection == 0 && player.grounded) {
		if(player.velocity.x > 0) {
			player.velocity.x -= 1;
			if(player.velocity.x < 0) {
				player.velocity.x = 0;
			}
		} else if(player.velocity.x < 0) {
			player.velocity.x += 1;
			if(player.velocity.x > 0) {
				player.velocity.x = 0;
			}
		}
	} 

	player.velocity.x += xdirection * player.speed;

	if(player.velocity.x > maxSpeed) {
		player.velocity.x = maxSpeed;
	} else if(player.velocity.x < -maxSpeed) {
		player.velocity.x = -maxSpeed;
	}

	tools.globalAlpha = 1;
	var image = new Image();
	image.src = 'images/grass.png';

	var howManyBackgroundsIn = Math.floor((player.position.x + 500) / 1920);
	var startX = howManyBackgroundsIn * 1920;
	var howFarIntoTheImage = player.position.x - 500 - startX;
	tools.drawImage(image, startX - howFarIntoTheImage, 740 + player.position.y, 1920, 259);
	var leftBackgroundX = player.position.x - 500;
	var howManyBackgroundInAreWe = leftBackgroundX / 1920;

	// gamecan.width

	for(var index = 0; index < gameObjects.length; index++) {
		var gameObject = gameObjects[index];

        if(gameObject.tags.indexOf('enemy') != -1) {
            if (roboFreeze == false) {
			gameObject.think();
			}
		}

		for(var colliderIndex = 0; colliderIndex < gameObjects.length; colliderIndex++) {
			var collider = gameObjects[colliderIndex];

			if(collider == gameObject) {
				continue;
			}

			var collision = checkCollision(gameObject, collider);
			if(collision) {
				if(gameObject == player) {
					if(collider.tags.indexOf('jumpBoost') != -1) {
						jumpBoosts += 8;
						jumpBoost.destroy();
						jumpBoost = new GameObject(Math.random() * 10000, -100, 20, 20, "images/jump.png");
                        jumpBoost.tags.push('jumpBoost');
					}

					if(collider.tags.indexOf("coin") != -1) {
						coinAmount ++;
						collider.destroy();
					}
					
					if(collider.tags.indexOf("metal") != -1) {
						metalAmount ++;
						collider.destroy();
					}

					if(collider.tags.indexOf('powerUp') != -1) {
						powerShots += 20;
						powerUp.destroy();
					
					}  if (collider.tags.indexOf('healthBoost') != -1) {
						healthBoosts = 5;
						healthBoost.destroy();
						healthBoost = new GameObject(Math.random() * 10500, -100, 30, 30,"images/health.png");
						healthBoost.tags.push("healthBoost");
					}
					if(collider.static && cheat < 2) {
						// player.speed = normalAcceleration;
						maxSpeed = 4;
						
						
					}
						if(collider.tags.indexOf('underground') != -1) {
							// player.speed = normalAcceleration;
							maxSpeed = 4;
							gameObject.velocity.y = 6;
						
					}
				} 

				if(gameObject.tags.indexOf('projectile') != -1) {
					if(collider.static) {
						// it is a projectile
						if(kazuyaMode == false) {
						gameObject.destroy();
						} else {
						if(ghost == false) {
						gameObject.velocity.y = 0;	
						}
						
						}
					} else if(collider.tags.indexOf('enemy') != -1 && cheat > 1) {
						collider.changeHealth (-100);
					} else if (collider.tags.indexOf('enemy') != -1 && cheat < 2){
						collider.changeHealth(-15);
					
					
					} if(collider.tags.indexOf('enemy') != -1 && powerShots > 0) {
						collider.changeHealth(-100);
						powerShots--;
					
					} if(collider.tags.indexOf('enemy') != -1 && activeWeapon == 'laser' && laserUpgrade == true) {
						collider.changeHealth(-100);
					}
					
				}

				if(gameObject.tags.indexOf('enemy') != -1) {
					if(collider.tags.indexOf('fortWall') != -1) {
						gameObject.status = "blocked";
					}
				}

				if (gameObject.tags.indexOf("fortRoof") != -1) {
					if(collider.tags.indexOf("fortWall") != -1) {
						gameObject.static = true;
						gameObject.velocity.y = 0;
					}
				}

				if(gameObject.tags.indexOf('character') != -1 && gameObject.tags.indexOf('enemy') == -1) {
				    if(collider.tags.indexOf('enemy') != -1) {
						if(imortal == false) {
						
						if(collider.type == 'heavy') {
				        	gameObject.changeHealth(-25);
				        	var differenceVector = gameObject.position.subtract(collider.position);
				        	differenceVector.normalize();
				        	differenceVector.scale(10);
				        	player.velocity = player.velocity.add(differenceVector);
				        } else {
				        	gameObject.changeHealth(-1);
							
							 }
						}
				        
				    }
				}

				if(collider.static) {
					if(gameObject.tags.indexOf("nuke") != -1) {
						document.body.style.backgroundColor = "rgb(255, 78, 34)";
						gameObject.destroy();

						for (var enemyIndex = 0; enemyIndex < enemies.length; enemyIndex++) {
							var enemy = enemies[enemyIndex]
							enemy.defeat();
						}

						// while(enemies.length) {
						// 	var enemy = enemies.pop();
						// 	enemy.defeat();
						// }

						setTimeout(function() {
							document.body.style.transition = "background-color 10s";
							document.body.style.backgroundColor = 'white';
						}, 3000);
					}

					gameObject.velocity.y = 0;
					gameObject.grounded = true;
				}
			}
		}

		if(gameObject.static == false && gameObject.grounded == false && gameObject.kinematic == false) {
			gameObject.velocity.y -= 0.08;
		}

		gameObject.position.x += gameObject.velocity.x;
		gameObject.position.y += gameObject.velocity.y;

		if(gameObject == player) {
			var image = new Image();
			if (kazuyaMode == false){
			image.src = 'images/player.gif';
			
			} else if (kazuyaMode == true) {
			image.src = 'images/kazuyaCannon.png';
			player.w = 200;
			}
			tools.globalAlpha = player.opacity;
			tools.drawImage(image, 500, 500, player.w, player.h);

			var image = new Image();
			if(activeWeapon == null) {
			if(kazuyaMode == false) {
			image.src = 'images/gun.png';
			} else {
			image.src = 'images/null.png'
			}
			tools.drawImage(image, 535, 530, 50, 50);
			} else if(activeWeapon == 'laser'){
			image.src = 'images/LazerGun.png';
			tools.drawImage(image, 535, 530, 50, 50);
			}
		} else {
		    tools.globalAlpha = gameObject.opacity;

			if(gameObject.image) {
				var image = new Image();
				image.src = gameObject.image;
				tools.drawImage(image, gameObject.position.x - (player.position.x - 500), -(gameObject.position.y - (player.position.y + 500)), gameObject.w,gameObject.h);
			} else {
				tools.fillStyle = gameObject.color;
				tools.fillRect(
					gameObject.position.x - (player.position.x - 500),
					
					-(gameObject.position.y - (player.position.y + 500)),
					gameObject.w,
					gameObject.h
				);
			}
		}
	}

	tools.font = '36px Arial';
	tools.fillText(score, 10, 40);
	tools.fillText(Math.floor(timer / 1000), gamecan.width - 100, 40);

	tools.font = '36px Arial';
	tools.fillText("coins: " + coinAmount, 10, 100);
	
	tools.font = '36px Arial';
	tools.fillText("metal: " + metalAmount, 10, 150);

	lastTime = currentTime;

	setTimeout(update, 15);
}

update();


function checkCollision(a,b) {
	var lxa = a.position.x;
	var rxa = a.position.x + a.w;
	var tya = a.position.y;
	var bya = a.position.y - a.h;

	var lxb = b.position.x;
	var rxb = b.position.x + b.w;
	var tyb = b.position.y;
	var byb = b.position.y - b.h;

	if(rxa < lxb || rxb < lxa || tyb < bya || tya < byb) {
		return false;
	} else {
		return true;
	}
}