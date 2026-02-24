Food Recall Alert - Database Access Guide
Last Updated: February 23, 2026
For: Capstone Team Members
Purpose: Access our PostgreSQL database using DBeaver

What You're Getting Access To
Our project uses AWS RDS PostgreSQL to store:

Product information (UPCs, names, brands)
Food recall data (FDA/USDA recalls)
User accounts and shopping carts
Alert history
Step 1: Download and Install DBeaver
For Mac Users:

Go to https://dbeaver.io/download/
Click "macOS"
Download the .dmg file
Open the .dmg and drag DBeaver to your Applications folder
Open DBeaver from Applications
For Windows Users:

Go to https://dbeaver.io/download/
Click "Windows (installer)"
Download and run the installer
Follow the prompts and launch DBeaver
For Linux Users:

Go to https://dbeaver.io/download/
Choose your distribution and follow the instructions
Step 2: Get the Required Files from the Team Lead
You'll need two things from Bryce before you can connect:

What	Details
SSH key file	food-recall-keypair.pem — the private key for the EC2 server
DB password	The PostgreSQL password for the postgres user
⚠️ Keep both of these secure. Never commit them to GitHub or share publicly.

Step 3: Set Up the Database Connection in DBeaver
Our RDS database lives inside a private AWS network. You cannot connect to it directly — DBeaver must tunnel through our EC2 server first. The setup has two parts: the main database connection, and the SSH tunnel.

3a. Create a New Connection
Open DBeaver

Click Database → New Database Connection (or click the 🔌 plug icon)

Select PostgreSQL and click Next

Enter the following on the Main tab:

Field	Value
Host	food-recall-db.cwbmyoom67nu.us-east-1.rds.amazonaws.com
Port	5432
Database	food_recall
Username	postgres
Password	(ask team lead)
☑️ Check Save password locally

3b. Configure the SSH Tunnel ← New — required!
Without this step the connection will time out. Our database is in a private network that can only be reached through the EC2 server.

In the same connection dialog, click the SSH tab at the top

Check Use SSH Tunnel

Fill in the SSH settings:

Field	Value
Host/IP	98.93.18.139
Port	22
Username	ubuntu
Authentication	Public Key
Private Key	Click Browse → select your food-recall-keypair.pem file
Click Test tunnel configuration — it should say Connected ✅

Mac/Linux note: If you get a "permissions" error on the .pem file, open Terminal and run:

chmod 600 ~/Downloads/food-recall-keypair.pem

Then try the tunnel test again.

3c. Test and Finish
Go back to the Main tab
Click Test Connection
If prompted to download PostgreSQL drivers, click Download, wait, then test again
Should say Connected ✅
Click Finish
You should now see the database in the left sidebar!

Step 4: Explore the Database
In the left sidebar, expand:

food_recall → Schemas → public → Tables

You'll find these tables:

Table	What's in it
users	Registered accounts (name, email, hashed password)
products	Product catalog (UPC, name, brand, category, ingredients)
recalls	FDA/USDA recall records
user_carts	Each user's saved grocery list
alerts	Recall alerts generated for users
To run a query: Right-click any table → View Data, or click the SQL editor icon and type your query.
