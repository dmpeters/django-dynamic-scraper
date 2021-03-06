from django.db import models
from dynamic_scraper.models import ScraperRuntime, SchedulerRuntime
from scrapy.contrib_exp.djangoitem import DjangoItem


class EventWebsite(models.Model):
    name = models.CharField(max_length=200)
    scraper_runtime = models.ForeignKey(ScraperRuntime, blank=True, null=True, on_delete=models.SET_NULL)
    
    def __unicode__(self):
        return self.name + " (" + str(self.id) + ")"


class Event(models.Model):
    title = models.CharField(max_length=200)
    event_website = models.ForeignKey(EventWebsite) 
    description = models.TextField(blank=True)
    url = models.URLField()
    checker_runtime = models.ForeignKey(SchedulerRuntime, blank=True, null=True, on_delete=models.SET_NULL)
    
    def __unicode__(self):
        return self.title + " (" + str(self.id) + ")"


class EventItem(DjangoItem):
    django_model = Event