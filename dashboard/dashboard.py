from trac.core import *
from pkg_resources import resource_filename
from trac.config import Option, IntOption, ListOption, BoolOption
from trac.web.api import IRequestHandler, Href
from trac.util.translation import _
from trac.web.chrome import add_stylesheet, add_script, INavigationContributor, ITemplateProvider
from trac.web.chrome import Chrome
from trac.util.datefmt import utc, to_timestamp
from genshi.template import TemplateLoader
from genshi.filters.transform import Transformer
from trac.web.api import ITemplateStreamFilter
from trac.perm import IPermissionRequestor
from trac.util import escape, Markup

import time
from datetime import datetime, timedelta




class DashBoard(Component):
    implements(IRequestHandler, ITemplateProvider, IPermissionRequestor, INavigationContributor)
    
    permission = Option('dashboard', 'permission', '')
    default_milestone = Option('dashboard', 'default_milestone', '')

    def __init__(self):
        self.db = self.env.get_db_cnx()
        self.username = None
        self.backDate = 30
        self.ticket_closed = ['checkedin', 'closed']

        self.ticket_closed_sql = "','".join(self.ticket_closed)

        self.milestone = self.default_milestone
        
        if self.permission:
            self.perm = self.permission
        else:
            self.perm = 'DASHBOARD_VIEW'

        self.env.log.debug("Using Permission: %s" % self.permission)

    
    # INavigationContributor methods
    def get_active_navigation_item(self, req):
        return 'dashboard'

    def get_navigation_items(self, req):
        if self.perm in req.perm or 'TRAC_ADMIN' in req.perm:
            yield 'mainnav', 'dashboard', Markup('<a href="%s">Dashboard</a>' % (
                    self.env.href.dashboard() ) )



    def get_permission_actions(self):
        yield self.perm

   
    # IRequestHandler methods
    def match_request(self, req):
        serve = False
        self.env.log.debug("Match Request")


        uri = req.path_info.lstrip('/').split('/')
        if uri[0] == 'dashboard':
            serve = True

        self.env.log.debug("Handle Request: %s" % serve)
        self.baseURL = req.href('dashboard', '/')
        self.baseQueryURL = req.href('query', '/')
        self.username = req.authname
        if 'milestone' in req.args:
            self.milestone = req.args.get('milestone')
        else:
            self.milestone = self.default_milestone

        if self.milestone == '':
            cursor = self.db.cursor()
            sql = "select name from milestone where (completed = 0) limit 0, 1"
            cursor.execute(sql)
            for name, in cursor:
                self.milestone = name

        if 'dev' in req.args:
            self.username = req.args.get('dev')
        else:
            self.username = req.authname

            return serve

        if not self.perm in req.perm:
            self.env.log.debug("NO Permission to view")
            return False

        return serve
 
    def get_updated_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status from ticket where (owner = '%s') and (changetime >= %s) and (status not in ('%s', 'new')) order by changetime desc" % (self.username, self.stamp, self.ticket_closed_sql)
        cursor.execute(sql)
        out = []
        idx = 0
        for id, component, summary, status in cursor:
            data = {
                '__idx__': idx,
                'id': id,
                'component': component,
                'summary': summary,
                'status': status
            }
            idx = idx + 1
            out.append(data)
        return out

    def get_new_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, status, component, summary, changetime, priority from ticket where (owner = '%s') and (status in ('new', 'assigned')) and (type = 'defect') order by changetime desc" % self.username
        cursor.execute(sql)
        out = []
        idx = 0
        for id, status, component, summary, changetime, priority in cursor:
            data = {
                '__idx__': idx,
                'id': id,
                'status': status,
                'component': component,
                'summary': summary,
                'priority': priority,
                'changetime': datetime.fromtimestamp(changetime, utc)
            }
            idx = idx + 1
            out.append(data)
        return out

    def get_closed_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, changetime, status from ticket where (owner = '%s') and (status in ('%s')) and (changetime >= %s) order by component, status, changetime desc" % (self.username, self.ticket_closed_sql, self.stamp)
        cursor.execute(sql)
        out = []
        idx = 0
        for id, component, summary, changetime, status in cursor:
            data = {
                '__idx__': idx,
                'id': id,
                'component': component,
                'summary': summary,
                'status': status,
                'changetime': datetime.fromtimestamp(changetime, utc)
            }
            idx = idx + 1
            out.append(data)
        return out

    def get_milestone_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status, priority from ticket where (owner = '%s') and (status not in ('%s', 'new')) and (type in ('defect', 'enhancement')) and (milestone = '%s') order by component, priority" % (self.username, self.ticket_closed_sql, self.milestone)
        cursor.execute(sql)
        out = []
        idx = 0
        for id, component, summary, status, priority in cursor:
            data = {
                '__idx__': idx,
                'id': id,
                'component': component,
                'summary': summary,
                'status': status,
                'priority': priority
            }
            idx = idx + 1
            out.append(data)
        return out

    def get_todo_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status from ticket where (owner = '%s') and (status not in ('%s')) and (type = 'task') order by changetime desc" % (self.username, self.ticket_closed_sql)
        cursor.execute(sql)
        out = []
        idx = 0
        for id, component, summary, status in cursor:
            data = {
                '__idx__': idx,
                'id': id,
                'component': component,
                'summary': summary,
                'status': status
            }
            idx = idx + 1
            out.append(data)
        return out

    def get_ticket_counts(self):
        cursor = self.db.cursor()
        sql = "select count(*) as total, type, status from ticket where (owner = '%s') and (status not in ('%s')) group by type, status order by total desc" % (self.username, self.ticket_closed_sql)
        cursor.execute(sql)
        out = []
        idx = 0
        for total, type, status in cursor:
            data = {
                '__idx__': idx,
                'total': total,
                'status': status,
                'type': type
            }
            idx = idx + 1
            out.append(data)

        return out

    def get_action_counts(self):
        cursor = self.db.cursor()
        #sql = "select count(*) as total, concat(oldvalue, ' => ', newvalue) as status from ticket_change where (author = '%s') and (time > %s) and (field = 'status') group by status order by total desc" % (self.username, self.stamp)
        sql = "select count(*) as total, (%s) as status from ticket_change where (author = '%s') and (time > %s) and (field = 'status') group by status order by total desc" % (self.db.concat('oldvalue', "' => '", 'newvalue'), self.username, self.stamp)
        cursor.execute(sql)
            
        out = []
        idx = 0
        for total, status in cursor:
            data = {
                '__idx__': idx,
                'total': total,
                'status': status
            }
            idx = idx + 1
            out.append(data)

        return out


    def get_milestone_data(self):
        cursor = self.db.cursor()
        out = {
            'total': 0,
            'closed': 0,
            'closed_percent': 0,
            'new': 0,
            'new_percent': 0,
            'inprogress': 0,
            'inprogress_percent': 0,
            'name': self.milestone
        }
        #sql = "select count(*) as total, ticket.status from ticket, ticket_custom where (ticket.milestone = '%s') and (ticket.owner = '%s') and (ticket.id = ticket_custom.ticket) and (ticket_custom.name = 'location') and (ticket_custom.value = 'Library Code')"  % (self.milestone, self.username)
        sql = "select count(*) as total, status from ticket where (milestone = '%s') and (owner = '%s') and (type = 'defect') group by status" % (self.milestone, self.username)
        cursor.execute(sql)

        for total, status in cursor:
            out['total'] = out['total'] + total

            if status in self.ticket_closed:
                out['closed'] = out['closed'] + total
            elif status == 'new':
                out['new'] = out['new'] + total
            else:
                out['inprogress'] = out['inprogress'] + total

        if out['closed'] > 0:
            out['closed_percent'] = int(round((float(out['closed']) / out['total']), 3) * 100)

        if out['new'] > 0:
            out['new_percent'] = int(round((float(out['new']) / out['total']), 1) * 100)

        if out['inprogress'] > 0:
            out['inprogress_percent'] = int(round((float(out['inprogress']) / out['total']), 3) * 100)


        return out

    def get_milestones(self):
        cursor = self.db.cursor()
        sql = "select name from milestone where (name not in ('%s')) and (completed = 0)" % self.milestone
        cursor.execute(sql)
        data = []
        for name, in cursor:
            data.append(name)

        return data

    def get_users(self):
        devs = self.env.get_known_users()
        odevs = []
        for username,name,email in devs:
            if username != self.username:
                data = {
                    'username': username,
                    'name': name or username
                }
                odevs.append(data)
        return odevs


    def process_request(self, req):
        data = {}
        self.stamp = time.time() - (60 * 60 * 24 * self.backDate)
        today = datetime.now(req.tz)


        data['backDate'] = self.backDate
        data['stamp'] = self.stamp
        data['username'] = self.username
        data['milestone'] = self.milestone

        #Updated Tickets 
        data['updated_tickets'] = self.get_updated_tickets()
        data['has_updated_tickets'] = len(data['updated_tickets'])

        #New Tickets
        data['new_tickets'] = self.get_new_tickets()
        data['has_new_tickets'] = len(data['new_tickets'])

        #Closed Tickets
        data['closed_tickets'] = self.get_closed_tickets()
        data['has_closed_tickets'] = len(data['closed_tickets'])

        #Ticket Counts
        data['ticket_counts'] = self.get_ticket_counts()
        data['has_ticket_counts'] = len(data['ticket_counts'])

        #Action Counts
        data['action_counts'] = self.get_action_counts()
        data['has_action_counts'] = len(data['action_counts'])

        #TODO Lists
        data['todo_tickets'] = self.get_todo_tickets()
        data['has_todo_tickets'] = len(data['todo_tickets'])

        #Milestones
        data['milestone_data'] = self.get_milestone_data()
        data['has_milestones'] = len(data['milestone_data'])

        #Milestone Tickets
        data['milestone_tickets'] = self.get_milestone_tickets()
        data['has_milestone_tickets'] = len(data['milestone_tickets'])

        #Milestones
        data['milestones'] = self.get_milestones()

        #Users
        data['users'] = self.get_users()


        add_script(req, "dashboard/dashboard.js")
        add_stylesheet(req, "dashboard/dashboard.css")
        return 'dashboard.html', data, None


    def get_htdocs_dirs(self):
        """Return the absolute path of a directory containing additional
        static resources (such as images, style sheets, etc).
        """
        return [('dashboard', resource_filename(__name__, 'htdocs'))]
 
    def get_templates_dirs(self):
        """Return the absolute path of the directory containing the provided
        genshi templates.
        """
        rtn = [resource_filename(__name__, 'templates')]
        return rtn
