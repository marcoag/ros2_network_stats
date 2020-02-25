#!/usr/bin/env python3

import sys, select, os
from time import sleep
import asyncio
from io import StringIO
import signal

import pandas as pd
import matplotlib.pyplot as plt

def standarize_bw(value):
    if value[-1] == 'K':
        return float(value[:-1]) * 1000
    elif value[-1] == 'M':
        return float(value[-1]) * 1000000
    elif value[-1] == 'G':
        return float(value[-1]) * 1000000000
    else:
        return value

class NetworkStats:
    
    def __init__(self, config_file, log_dir, interface='lo'):
        self.log_dir = log_dir
        self.config_file = config_file
        self.latency_processes = []
        self.bw_topic_processes = []
        self.delay_topic_processes =[]
        self.hosts = []
        self.ros2_topics = []
        self.interface = interface
        
        
    def parse_config_file(self, filename=''):
     
        if filename:
            self.config_file = filename 
        
        with open(self.config_file, 'r') as f:
            hosts = f.readlines()
            for host in hosts:
                self.hosts.append(host.strip()) 
    
    async def save_topics_to_file(self, filename='monitored_topics.log'):
        #Get all current topics
        with open('{}/{}'.format(self.log_dir, filename), 'w') as file_topics:
            process = await asyncio.subprocess.create_subprocess_exec(
                        'ros2', 'topic', 'list',
                        stdout=file_topics)
        await process.wait()
        
    def load_topics_from_file(self, filename='monitored_topics.log'):
        with open('{}/{}'.format(self.log_dir, filename), 'r') as file_topics:
            for topic in file_topics:
                self.ros2_topics.append(topic.strip())
    
            
    async def traceroute(self, host):
        with open('{}/{}_traceroute.log'.format(self.log_dir, host), 'w') as file_traceroute:
            return await asyncio.subprocess.create_subprocess_exec('traceroute', host, stdout=file_traceroute)

    async def latency(self, host):
        with open('{}/{}_latency.log'.format(self.log_dir, host), 'w') as file_ping:
            return await asyncio.subprocess.create_subprocess_exec('ping', host, stdout=file_ping)
    
    async def bw_topic(self, topic):
        with open('{}/{}_topic_bw.log'.format(self.log_dir, topic.replace('/', '__')), 'w') as file_bw_topic:
            return await asyncio.subprocess.create_subprocess_exec('ros2', 'topic', 'bw', topic, stdout=file_bw_topic)
        
    async def delay_topic(self, topic):
        with open('{}/{}_topic_delay.log'.format(self.log_dir, topic.replace('/', '__')), 'w') as file_delay_topic:
            return await asyncio.subprocess.create_subprocess_exec('ros2', 'topic', 'delay', topic, stdout=file_delay_topic)
        
    async def full_bandwidth(self, filename='bw.log'):
        self.bw_file = open('{}/{}'.format(self.log_dir, filename), 'w')
        process = await asyncio.subprocess.create_subprocess_exec('ifstat',
                                  '-nti',
                                  self.interface,
                                  '0.5',
                                  stdout=self.bw_file)
        asyncio.ensure_future(process.wait())
        
    async def traceroute_to_all_hosts(self):
        for host in self.hosts:
            await asyncio.ensure_future(self.traceroute(host))
            
    async def monitor_latency_to_all_hosts(self):
        for host in self.hosts:
            self.latency_processes.append(await self.latency(host))
            
    async def monitor_bandwdith_from_all_topics(self):
        for topic in self.ros2_topics:
            self.bw_topic_processes.append(await self.bw_topic(topic))
    
    async def monitor_delay_from_all_topics(self):
        for topic in self.ros2_topics:
            self.delay_topic_processes.append(await self.delay_topic(topic))
         
         
    ## reports
    def create_full_bandwidth_report(self, filename='bw.log'):
        
        data = pd.read_csv('{}/{}'.format(self.log_dir, filename),
                               sep=r'\s*',
                               skiprows=2,
                               header=None)
        data.rename(columns={0: 'Time', 1: 'in', 2: 'Out'}, inplace=True)
        data['Time'] = pd.to_datetime(data['Time'],
                                        format='%H:%M:%S').dt.time
        data.plot(x='Time', figsize=(20,15))
        #plt.plot(data['Time'], label='Time')
        plt.ylabel('Bandwidth') 
        plt.savefig('{}/{}'.format(self.log_dir, filename).replace('.log', '.png'))
        plt.close()
        
        
    def create_latency_reports(self):
        for f in os.listdir(self.log_dir):
            if f.endswith('_latency.log'):
                
                with open('{}/{}'.format(self.log_dir,f), 'r') as latency_file_data:
                    #skip the top info line
                    line = latency_file_data.readline()
                    line = latency_file_data.readline()
                    latency = []
                    while line.strip() != '':
                        
                        list_fields = line.split()
                        sub = 'time='
                        latency.append(float(
                            [s for s in list_fields if sub in s][0]
                            .replace('time=','')))

                        line = latency_file_data.readline()
                        
                if latency:
                    plt.figure(figsize=(20,15), dpi=150)
                    plt.plot(latency, label='latency')
                    plt.legend()
                    plt.ylabel('ms')
                    plt.locator_params(axis='y', nbins=6)                 
                    plt.savefig('{}/{}'.format(self.log_dir,f).replace('.log', '.png'))
                    plt.close()
    
    def create_bandwidth_reports(self):
        for f in os.listdir(self.log_dir):
            if f.endswith('_topic_bw.log'):
                with open('{}/{}'.format(self.log_dir,f), 'r') as topic_file_read:
                    # Skip until the lines containing data
                    line = topic_file_read.readline()
                    while line and not line.startswith('average'):
                        line = topic_file_read.readline()
                    average_values = []
                    mean_values = []
                    min_values = []
                    max_values = []
                    while line:
                        if line.startswith('average'):
                            average_values.append(standarize_bw(
                                line.split(' ')[1].split('B')[0]))
                        else:
                            line = line.split(' ')
                            mean_values.append(standarize_bw(line[1][:-1]))
                            min_values.append(standarize_bw(line[3][:-1]))
                            max_values.append(standarize_bw(line[5][:-1]))
                        line = topic_file_read.readline()
                    if average_values:
                        plt.figure(figsize=(20,15), dpi=150)
                        plt.plot(average_values, label='average')
                        plt.plot(mean_values, label='mean')
                        plt.plot(min_values, label='min')
                        plt.plot(max_values, label='max')
                        plt.legend()
                        plt.gca().invert_yaxis()
                        plt.locator_params(axis='y', nbins=6)
                        plt.savefig('{}/{}'.format(self.log_dir,f).replace('.log', '.png'))
                        plt.close()
    
    #if only there were any!
    def create_delay_reports(self):
        for f in os.listdir(self.log_dir):
            if f.endswith('_topic_delay.log'):
                print(f)
            
            
    def killemall(self):
        for p in self.latency_processes:
            if p:
                try:
                    p.send_signal(signal.SIGINT)
                except ProcessLookupError as e:
                    print('ProcessLookupError' + str(e))
                    
        for p in self.bw_topic_processes:
            if p:
                try:
                    p.send_signal(signal.SIGINT)
                except ProcessLookupError as e:
                    print('ProcessLookupError' + str(e))
                    
        for p in self.delay_topic_processes:
            if p:
                try:
                    p.send_signal(signal.SIGINT)
                except ProcessLookupError as e:
                    print('ProcessLookupError' + str(e))
                    
    def __del__(self):
        self.killemall()
            
            

async def main(loop, config_file, log_dir):
    
    network_stats  = NetworkStats(config_file, log_dir)
    
    ##read hosts from config file
    #network_stats.parse_config_file()
    
    ##Run a traceroute to all
    #await network_stats.traceroute_to_all_hosts()
        
        
    #await network_stats.save_topics_to_file('monitored_topics.log')
    #network_stats.load_topics_from_file()
    
    ##spawn monitoring network stats
    
    #await network_stats.full_bandwidth()
    #await network_stats.monitor_latency_to_all_hosts()
    #await network_stats.monitor_bandwdith_from_all_topics()
    #await network_stats.monitor_delay_from_all_topics()
            
    
    #while True:
        #print('ruinning bandwidth latency tests')
        #if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            
            ##killing all network monitoring processes
            #network_stats.killemall()
            #break
        #sleep(1)
        
    network_stats.create_full_bandwidth_report()
    network_stats.create_latency_reports()
    network_stats.create_bandwidth_reports()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('You need to provide a list of IPs in the network and route to save data')
        exit(1)
    else:

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main(loop, sys.argv[1], sys.argv[2]))
        finally:
            loop.close()
