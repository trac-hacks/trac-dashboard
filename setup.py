from setuptools import find_packages, setup

# name can be any name.  This name will be used to create .egg file.
# name that is used in packages is the one that is used in the trac.ini file.
# use package name as entry_points

setup(
    name='Trac-Dashboard',
    version='0.1',
    author='Dav Glass',
    author_email='davglass@gmail.com',
    description = "Creates a developer dashboard.",
    license = """BSD""",
    url = "http://github.com/davglass/trac-dashboard/tree/master",
    packages = find_packages(exclude=['*.tests*']),
    package_data={'dashboard': ['templates/*.html', 'htdocs/*']},

    install_requires = [
        '',
    ],
    entry_points = {
        'trac.plugins': [
            'dashboard = dashboard',

        ]    
    }

)
