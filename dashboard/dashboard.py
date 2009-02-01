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

import time
from datetime import datetime, timedelta




class DashBoard(Component):
    implements(IRequestHandler, ITemplateProvider, IPermissionRequestor)
    
    permission = ListOption('dashboard', 'permission', '')
    

    def __init__(self):
        self.db = self.env.get_db_cnx()
        self.perm = self.config.get('dashboard', 'permission', '').upper()
        self.username = None
        self.backDate = 14
        self.ticket_closed = ['checkedin', 'closed']
        
        if not self.perm:
            self.perm = 'DASHBOARD_VIEW'

        self.env.log.debug("Using Permission: %s" % self.perm)


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
        if not self.perm in req.perm:
            self.env.log.debug("NO Permission to view")
            return False

        return serve
 
    def get_updated_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status from ticket where (owner = '%s') and (changetime >= %s) and (status not in ('checkedin', 'closed', 'new')) order by changetime desc" % (self.username, self.stamp)
        cursor.execute(sql)
        out = []
        for id, component, summary, status in cursor:
            data = {
                'id': id,
                'component': component,
                'summary': summary,
                'status': status
            }
            out.append(data)
        return out

    def get_new_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status from ticket where (owner = '%s') and (time >= %s) and (status = 'new') and (type = 'defect') order by changetime desc" % (self.username, self.stamp)
        cursor.execute(sql)
        out = []
        for id, component, summary, status in cursor:
            data = {
                'id': id,
                'component': component,
                'summary': summary,
                'status': status
            }
            out.append(data)
        return out

    def get_todo_tickets(self):
        cursor = self.db.cursor()
        sql = "select id, component, summary, status from ticket where (owner = '%s') and (changetime >= %s) and (status not in ('checkedin', 'closed')) and (type = 'task') order by changetime desc" % (self.username, self.stamp)
        cursor.execute(sql)
        out = []
        for id, component, summary, status in cursor:
            data = {
                'id': id,
                'component': component,
                'summary': summary,
                'status': status
            }
            out.append(data)
        return out

    def get_ticket_counts(self):
        cursor = self.db.cursor()
        sql = "select count(*) as total, status from ticket where (owner = '%s') and (changetime >= %s) and (type = 'defect') group by status" % (self.username, self.stamp)
        cursor.execute(sql)
        out = []
        for total, status in cursor:
            data = {
                'total': total,
                'status': status
            }
            out.append(data)

        return out

    def get_milestones(self):
        cursor = self.db.cursor()
        sql = "select count(*) as total, milestone from ticket where (owner = '%s') and (milestone <> '') group by milestone" % self.username
        cursor.execute(sql)
        out = []
        for total, milestone in cursor:
            data = {
                'total': total,
                'milestone': milestone
            }
            out.append(data)

        return out

    def get_milestone_data(self, milestones):
        cursor = self.db.cursor()
        stones = []
        out = {}
        for i in milestones:
            stones.append(i['milestone'])
            out[i['milestone']] = {
                'name': i['milestone'],
                'total': 0,
                'new': 0,
                'closed': 0,
                'inprogress': 0
            }

        sql = "select count(*) as total, status, milestone from ticket where (milestone in ('%s')) and (owner = '%s') and (type = 'defect') group by milestone, status" % ("','".join(stones), self.username)
        cursor.execute(sql)

        data = []
        count = 0
        new = 0
        closed = 0
        inprogress = 0

        for total, status, milestone in cursor:
            out[milestone]['total'] = out[milestone]['total'] + total

            if status in self.ticket_closed:
                out[milestone]['closed'] = out[milestone]['closed'] + total
            elif status == 'new':
                out[milestone]['new'] = out[milestone]['new'] + total
            else:
                out[milestone]['inprogress'] = out[milestone]['inprogress'] + total
        
        info = []
        for i in out:
            tmp = out[i]
            tmp['closed_percent'] = int(round((float(tmp['closed']) / tmp['total']), 3) * 100)
            tmp['new_percent'] = int(round((float(tmp['new']) / tmp['total']), 1) * 100)
            tmp['inprogress_percent'] = int(round((float(tmp['inprogress']) / tmp['total']), 3) * 100)
            info.append(tmp)

        self.env.log.debug(info)

        return info
        

    def process_request(self, req):
        data = {}
        self.stamp = time.time() - (60 * 60 * 24 * self.backDate)
        today = datetime.now(req.tz)
        
        data['backDate'] = self.backDate
        data['username'] = self.username
        #Updated Tickets 
        data['updated_tickets'] = self.get_updated_tickets()
        data['has_updated_tickets'] = len(data['updated_tickets'])
        #New Tickets
        data['new_tickets'] = self.get_new_tickets()
        data['has_new_tickets'] = len(data['new_tickets'])
        #Ticket Counts
        data['ticket_counts'] = self.get_ticket_counts()
        data['has_ticket_counts'] = len(data['ticket_counts'])
        #TODO Lists
        data['todo_tickets'] = self.get_todo_tickets()
        data['has_todo_tickets'] = len(data['todo_tickets'])
        #Milestones
        data['milestones'] = self.get_milestones()
        data['has_milestones'] = len(data['milestones'])

        data['milestone_data'] = self.get_milestone_data(data['milestones'])


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
