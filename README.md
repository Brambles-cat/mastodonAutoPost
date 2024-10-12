<h1 align="center">
  Mastodon Post Scheduler
</h1>

**Installation Guide**

# Step 1: Download
Download the repository either with git or with the download as zip functionality from github.

``git clone https://github.com/TheTop10PonyVideos/mastodonAutoPost.git``

# Step 2: .env file setup
Create a .env file and paste following lines into this file (use your editor)

``access_token = 'Your access token'``

``instance_url = 'your mastodon instance'``

**Where do I get an access token?**

1. Login into your mastodon account and click on preferences (can be found at the right side of your screen)
2. Go to </>Development and create a new application
3. Copy your access_token and paste it into your .env file.

# Step 3: Install required libaries:

``pip install -r requirements.txt``

# Step 4: Run the script

``python main.py``

# Step 5 : Convert to an .exe file

This step is optional and requires an additional libary: pyinstaller
Download it with the following command:

``pip install pyinstaller``

Once you did that you can now convert you python script into a .exe file!
Use this command:

``pyinstaller --name MastodonAutoScheduler --onefile main.py``
