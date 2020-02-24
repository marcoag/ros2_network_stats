#!/usr/bin/env python3

import sys, select, os
from time import sleep
import asyncio
from io import StringIO
import signal

def parse_config_file(filename):

    with open(filename, 'r') as f:
        ips = f.readlines()
        return [ip.strip() for ip in ips]

async def traceroute(ip, log_dir):
    with open('{}/{}_traceroute.log'.format(log_dir, ip), 'w') as file_traceroute:
        return await asyncio.subprocess.create_subprocess_exec('traceroute', ip, stdout=file_traceroute)

async def ping(ip, log_dir):
    with open('{}/{}_ping.log'.format(log_dir, ip), 'w') as file_ping:
        return await asyncio.subprocess.create_subprocess_exec('ping', ip, stdout=file_ping)
    
async def bw_topic(topic, log_dir):
    with open('{}/{}_topic_bw.log'.format(log_dir, topic.replace('/', '__')), 'w') as file_bw_topic:
        return await asyncio.subprocess.create_subprocess_exec('ros2', 'topic', 'bw', topic, stdout=file_bw_topic)

async def main(loop, ips, log_dir):
    #Run traceroute to all ips
    #await asyncio.gather(*[traceroute(ip, log_dir) for ip in ips])
    for ip in ips:
        await asyncio.ensure_future(traceroute(ip, log_dir))
    
    #Get all current topics
    with open('{}/monitored_topics.log'.format(log_dir), 'w') as file_topics:
        process = await asyncio.subprocess.create_subprocess_exec(
                    'ros2', 'topic', 'list',
                    stdout=file_topics)
    await process.wait()
        
    #Monitor IPs 
    ping_process = []
    for ip in ips:
        ping_process.append(await ping(ip, log_dir))
        
    #Monitor topic bw and delay
    bw_topic_process = []
    delay_topic_process = []
    with open('{}/monitored_topics.log'.format(log_dir), 'r') as file_topics:
        for topic in file_topics:
            bw_topic_process.append(await bw_topic(topic.strip(), log_dir))
            
    
    
    while True:
        print('ruinning bandwidth latency tests')
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            #should kill tracroutes? 
            #killing all ping process and closing their files
            for p in ping_process:
                p.terminate()
            for p in bw_topic_process:
                if p:
                    try:
                        p.send_signal(signal.SIGINT)
                    except ProcessLookupError as e:
                        print('ProcessLookupError' + str(e))
                
            break
        sleep(1)
    
    #Monitor topic bw
    
    #Monitor topic delay
    
    
 

    #for topic in iter(process.stdout.readline, ''):
        #print(topic.strip())


if __name__ == '__main__':
    """Entry point for """
    if len(sys.argv) < 3:
        print('You need to provide a list of IPs in the network and route to save data')
        exit(1)
    else:
        print('Reading IPs to monitor from {}'.format(sys.argv[1])) 
        ips = parse_config_file(sys.argv[1])
        print(ips)

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main(loop, ips, sys.argv[2]))
        finally:
            loop.close()
        





#while True:
#    print('starting bandwidth latency tests')
#    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
#        line = raw_input()
#        break
#    sleep(1)
