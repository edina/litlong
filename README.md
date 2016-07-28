#LitLong ReadMe

#Server Configuration

Server ssh account passwords are in the password file. There are two user accounts:

- paladmin (user with sudo privileges)
- palimp (standard user account where application is installed)

##Database

The live application runs off of a local version of PostgreSQL database installed on the live server. Configuration details for this can be found at:

    /home/palimp/dist/current/etc/yamjam/config.xml

##Deploy new version of site

This requires a local copy of the project cloned from GitLab. From the local copy:

    cd <REPO_ROOT>
    fab host.production release.deploy release.cleanup

See the `fabfile` directory for details.

##Web server

###Start

    sudo service nginx start

###Stop
    
    sudo service nginx stop

###Restart

    sudo service nginx restart


##Application server

This application server is controlled via [Supervisor](http://supervisord.org/)

###Start

    sudo supervisorctl start litlong

###Stop
    
    sudo supervisorctl stop litlong
    
###Restart

    sudo supervisorctl restart litlong
    
If the application is just giving 500 errors then it's possible that SELinux has been enabled. Once this is turned off the app should start working again.

If supervisor isn't running it can be started by

    sudo service supervisord start
    
##Clearing Web & Memcache Caches

Sometimes after deploying a new version of the site the web and memcache caches need to be emptied

###Empty Nginx Cache

    sudo supervisorctl restart litlong
    cd /var/cache/nginx
    sudo service nginx stop
    sudo rm -r *
    sudo service nginx start
    
###Empty memcached

    echo 'flush_all' | nc localhost 11211
    
#Parser

This runs locally and parses the data from a series of XML files into a local spatially enabled PostgreSQL database.

##Clone Repo

    git clone git@gitlab.edina.ac.uk:ian.fieldhouse/litlong.git litlong-dev
    
##Create Virtual Environment

Install [`pyenv`](https://github.com/yyuu/pyenv) and [`pyenv-virtualenv`](https://github.com/yyuu/pyenv-virtualenv)

    cd <REPO_ROOT>
    pyenv install <PYTHON_VERSION>
    pyenv virtualenv <PYTHON_VERSION> litlong-dev
    pyenv activate litlong-dev
    
##Install Requirements

    cd <REPO_ROOT>
    pip install -r etc/requirements/parser.txt

##Create Spatial Database

    createdb litlong-dev --owner=<USERNAME>
    psql -d litlong-dev -U <USERNAME> -c "CREATE EXTENSION postgis;"

##Create Database Tables

    cd <REPO_ROOT>/site
    ./manage.py migrate --settings=litlong.local_settings   

##Create a YamJam configuration file

The project uses [YamJam](http://yamjam.readthedocs.io/) for keeping configuration out of source control.

Create a new YamJam config file base on the sample

     cd <REPO_ROOT>/etc/YamJam
     cp config.xml.sample config.xml
    
Fill in the configuration file with the details from the live server and update the `local` database configuration to the database you have just created.

##Parse Documents

Make sure PYTHONPATH environment variable is set to current directory
    
    cd <REPO_ROOT>/site
    export PYTHONPATH=.
    
###Run the parser

    cd <REPO_ROOT>/site
    python ./api/scripts/parser.py -d ../etc/sample-xml
    
##Add Full Text Search Table

Add the full text search table for the parsed data to the database.

    DROP TABLE sentence_fts
        CREATE TABLE sentence_fts AS
        SELECT api_sentence.id AS sentence_id, to_tsvector(api_sentence.text) AS fts_tokens
        FROM api_sentence 
        WHERE api_sentence.palsnippet IS TRUE


#Running Application Locally

If the local database contains parsed data and the full text search table exists then the application can be run locally.

    ./manage.py runserver --settings=litlong.local_settings

    
    
