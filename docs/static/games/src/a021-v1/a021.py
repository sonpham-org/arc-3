"""a021 Delayed Rudder -- predict queued steering through a moving channel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,CHANNEL,BOAT,WAKE,QUEUE,BUOY,GOAL,BAD=0,10,8,14,6,11,12,13,15
LEVELS=[{"name":"First Queue","seq":(1,3)},{"name":"Delayed Turn","seq":(2,3)},{"name":"Wake Estimate","seq":(1,2,3)},{"name":"Moving Channel","seq":(4,2,1,3)},{"name":"Predictive Rudder","seq":(2,3,1,4,2,1,3)},{"name":"Delayed Rudder","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,delay,queue,wakes,channel,docked=s;x,y=pos;q=list(queue)
 if a in (1,2):q.append(-1 if a==1 else 1);q=q[-delay:];turn=q.pop(0) if len(q)>=delay else 0;y=(y+turn)%7;x=(x+1)%10
 elif a==3:wakes=wakes+((pos,tuple(q),delay,channel),)
 elif a==4:channel=(channel+1)%5;x=(x+1)%10;y=(y+(channel%3)-1)%7
 elif a==5:docked=((x,y),delay,tuple(q),wakes[-4:],channel)
 return (x,y),delay,tuple(q),wakes,channel,docked
for x in LEVELS:
 s=((0,3),2,(),(),1,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for x in range(10):cy=(g.channel+x)%5+1;f[8+cy*6:13+cy*6,6+x*5:11+x*5]=CHANNEL;f[14+cy*6:17+cy*6,6+x*5:11+x*5]=BUOY
  x,y=g.pos;f[8+y*6:14+y*6,6+x*5:11+x*5]=BOAT
  for i,q in enumerate(g.queue):f[51:56,8+i*12:17+i*12]=QUEUE if q>0 else WAKE
  for i,_ in enumerate(g.wakes[-3:]):f[57:60,8+i*14:18+i*14]=WAKE
  if g.docked:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A021(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a021",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=(0,3);self.delay=2;self.queue=();self.wakes=();self.channel=1;self.docked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.delay,self.queue,self.wakes,self.channel,self.docked=advance((self.pos,self.delay,self.queue,self.wakes,self.channel,self.docked),a)
  elif a==6:
   if (self.pos,self.delay,self.queue,self.wakes,self.channel,self.docked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
