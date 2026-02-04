BEGIN TRANSACTION;
CREATE TABLE client (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	phone VARCHAR, 
	email VARCHAR, 
	address VARCHAR, 
	notes VARCHAR, 
	credit_limit FLOAT, 
	razon_social VARCHAR, 
	cuit VARCHAR, 
	iva_category VARCHAR, 
	transport_name VARCHAR, 
	transport_address VARCHAR, 
	PRIMARY KEY (id)
);
INSERT INTO "client" VALUES(1,'Cliente Contado',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
CREATE TABLE payment (
	id INTEGER NOT NULL, 
	client_id INTEGER NOT NULL, 
	amount FLOAT NOT NULL, 
	date DATETIME NOT NULL, 
	note VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES client (id)
);
CREATE TABLE product (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	description VARCHAR, 
	barcode VARCHAR NOT NULL, 
	price FLOAT NOT NULL, 
	cost_price FLOAT NOT NULL, 
	stock_quantity INTEGER NOT NULL, 
	min_stock_level INTEGER NOT NULL, 
	category VARCHAR, 
	image_url VARCHAR, 
	cant_bulto INTEGER, 
	numeracion VARCHAR, 
	curve_quantity INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "product" VALUES(1,'Ojota lisa','Talle del 35/6 al 39/40','210 NEGRO',1750.0,0.0,100,5,'Verano-Ojotas Dama',NULL,12,'35-40',1);
INSERT INTO "product" VALUES(2,'Ojota faja lisa','Talle del 35/6 al 39/40','7059 NEGRO',4200.0,0.0,100,5,'Verano-Ojotas Dama',NULL,12,'35-40',1);
INSERT INTO "product" VALUES(3,'Gomones','Talle del 19/20 al 23/24','128BB ROSA',3500.0,0.0,100,5,'Verano-Gomones-BB',NULL,12,'19-24',1);
INSERT INTO "product" VALUES(4,'Faja','Talle del 35/6 al 39/40','795 NEGRO',5500.0,0.0,100,5,'Verano-Fajas-Dama',NULL,20,'35-40',1);
INSERT INTO "product" VALUES(5,'Sandalia velcro','Talle del 35/6 al 39/40','417BLANCO',13000.0,0.0,100,5,'Verano-Fajas-Dama',NULL,6,'35-40',1);
INSERT INTO "product" VALUES(6,'Entrededo','Talle del 37/38 al 43/44','401/6',3000.0,0.0,100,5,'Verano-Fajas-Hombre',NULL,25,'37-44',1);
CREATE TABLE sale (
	id INTEGER NOT NULL, 
	timestamp DATETIME NOT NULL, 
	total_amount FLOAT NOT NULL, 
	payment_method VARCHAR NOT NULL, 
	user_id INTEGER, 
	client_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(client_id) REFERENCES client (id)
);
CREATE TABLE saleitem (
	id INTEGER NOT NULL, 
	sale_id INTEGER, 
	product_id INTEGER, 
	product_name VARCHAR NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price FLOAT NOT NULL, 
	total FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sale_id) REFERENCES sale (id), 
	FOREIGN KEY(product_id) REFERENCES product (id)
);
CREATE TABLE settings (
	id INTEGER NOT NULL, 
	company_name VARCHAR NOT NULL, 
	logo_url VARCHAR NOT NULL, 
	currency_symbol VARCHAR NOT NULL, 
	printer_name VARCHAR, 
	PRIMARY KEY (id)
);
INSERT INTO "settings" VALUES(1,'NexPos','/static/images/logo.png','$',NULL);
CREATE TABLE tax (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	rate FLOAT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	full_name VARCHAR, 
	role VARCHAR NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "user" VALUES(1,'admin','$argon2id$v=19$m=65536,t=3,p=4$McYYo7TWmlMK4TzH+D9nbA$ZN1LTfRTBSLGF18uN9ArBHqMsS0LrJSQP2WA3zvSWLI','Administrador','admin',1);
CREATE INDEX ix_client_name ON client (name);
CREATE UNIQUE INDEX ix_user_username ON user (username);
CREATE UNIQUE INDEX ix_product_barcode ON product (barcode);
COMMIT;
