import datetime
from scrapy import log, signals
from scrapy.conf import settings
from scrapy.spider import BaseSpider
from scrapy.xlib.pydispatch import dispatcher
from scrapy.exceptions import CloseSpider

from django.core.exceptions import ObjectDoesNotExist

from dynamic_scraper.models import Log


class DjangoBaseSpider(BaseSpider):
    
    name = None
    action_successful = False
    allowed_domains = []
    start_urls = []
    conf = {
        "DO_ACTION": False,
        "RUN_TYPE": 'SHELL',
        "LOG_ENABLED": True,
        "LOG_LEVEL": 'ERROR',
        "LOG_LIMIT": 250,
    }
    command = 'scrapy crawl SPIDERNAME -a id=REF_OBJECT_ID [-a do_action=(yes|no) -a run_type=(TASK|SHELL)]'
    
    
    def _check_mandatory_vars(self, mandatory_vars):
        mandatory_vars.append('ref_object')
        mandatory_vars.append('scraper_runtime')
        
        if self.conf['RUN_TYPE'] == 'TASK' and not getattr(self, 'scheduler_runtime', None):
            msg = "You have to provide a scheduler_runtime when running with run_type TASK."
            log.msg(msg, log.ERROR)
            raise CloseSpider(msg)
        
        for var in mandatory_vars:
            attr = getattr(self, var, None)
            if not attr:
                msg = "Missing attribute %s (Command: %s)." % (var, self.command)
                log.msg(msg, log.ERROR)
                raise CloseSpider(msg)
    
    
    def _set_conf(self, **kwargs):
        if 'run_type' in kwargs:
            self.conf['RUN_TYPE'] = kwargs['run_type']
        if 'do_action' in kwargs:
            if kwargs['do_action'] == 'yes':
                self.conf['DO_ACTION'] = True
            else:
                self.conf['DO_ACTION'] = False
        
        self.conf['LOG_ENABLED'] = settings.get('DSCRAPER_LOG_ENABLED', self.conf['LOG_ENABLED'])
        self.conf['LOG_LEVEL'] = settings.get('DSCRAPER_LOG_LEVEL', self.conf['LOG_LEVEL'])
        self.conf['LOG_LIMIT'] = settings.get('DSCRAPER_LOG_LIMIT', self.conf['LOG_LIMIT'])
        
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)
                
    
    def _set_ref_object(self, ref_object_class, **kwargs):
        if not 'id' in kwargs:
            msg = "You have to provide an ID (Command: %s)." % self.command
            log.msg(msg, log.ERROR)
            raise CloseSpider(msg)
        try:
            self.ref_object = ref_object_class.objects.get(id=kwargs['id'])
        except ObjectDoesNotExist:
            msg = "Object with ID " + kwargs['id'] + " not found (Command: %s)." % self.command
            log.msg(msg, log.ERROR)
            raise CloseSpider(msg)
    
    
    def spider_closed(self):
        if self.conf['RUN_TYPE'] == 'TASK' and self.conf['DO_ACTION']:
            
            time_delta, factor, num_crawls = self.scheduler.calc_next_action_time(\
                    self.action_successful,\
                    self.scheduler_runtime.next_action_factor,\
                    self.scheduler_runtime.num_zero_actions)
            self.scheduler_runtime.next_action_time = datetime.datetime.now() + time_delta
            self.scheduler_runtime.next_action_factor = factor
            self.scheduler_runtime.num_zero_actions = num_crawls
            self.scheduler_runtime.save()
            msg  = "Scheduler runtime updated (Next action time: "
            msg += "%s, " % str(self.scheduler_runtime.next_action_time.strftime("%Y-%m-%d %H:%m"))
            msg += "Next action factor: %s, " % str(self.scheduler_runtime.next_action_factor)
            msg += "Zero actions: %s)" % str(self.scheduler_runtime.num_zero_actions)
            self.log(msg, log.INFO)
            
        if hasattr(self, 'scraper_runtime'):
            self.scraper_runtime.save()
    
    
    def log(self, message, level=log.DEBUG):
        if self.conf['RUN_TYPE'] == 'TASK' and self.conf['DO_ACTION']:
            
            if self.conf['LOG_ENABLED'] and level >= Log.numeric_level(self.conf['LOG_LEVEL']):
                l = Log()
                l.message = message
                l.ref_object = self.ref_object.__class__.__name__ + " (" + str(self.ref_object.id) + ")"
                l.level = int(level)
                l.spider_name = self.name
                if hasattr(self, 'scraper_runtime'):
                    l.scraper_runtime = self.scraper_runtime
                if hasattr(self, 'scraper'):
                    l.scraper = self.scraper
                l.save()
                
                #Delete old logs
                if Log.objects.count() > self.conf['LOG_LIMIT']:
                    items = Log.objects.all()[self.conf['LOG_LIMIT']:]
                    for item in items:
                        item.delete()
                
        super(DjangoBaseSpider, self).log(message, level)
        
    