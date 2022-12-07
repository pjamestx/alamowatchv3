# AlamoWatch - send alerts for new showtimes

### Overview

Downloads the latest showtimes for Alamo Theaters, loops through saved info for a known list of theaters,
and sends tweets/emails for any new movies detected.

### Setup

Basic python project, now updated for python 3.9

Set up virtual environment, then `pip install -r requirements.txt`

Copy `private_keys_example.py` to `private_keys.py` and supply the necessary Twitter/Gmail credentials

### Running

`python alamowatch_v3`  

(Does not currently require any runtime arguments, all config data is in settings files)  


### Notes

When adding new theaters, copy the `settings\_template.json` file and fill in the blanks  

To get the Twitter access token for each account, run  
`python get_access_token.py` and supply the user/pass for the account when the web page pops up

To disable checks for a theater (e.g. if they're closed for renovations), simple move the json file to the `disabled`
directory

Uses `python-twitter` library, https://github.com/bear/python-twitter
