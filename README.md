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
    
