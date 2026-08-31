"""a051 Priority Chute -- balance deadlines with starvation at one server."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,HALL,CHUTE,URGENT,ORDINARY,SERVER,AGE,OUTPUT,STARVE,BAD=11,8,9,12,14,10,13,6,4,15
LEVELS=[
 {"name":"Admit Urgent","seq":(1,)},{"name":"Serve Class","seq":(1,4)},
 {"name":"Age Ordinary","seq":(2,1,3,4)},{"name":"Avoid Starvation","seq":(1,2,1,3,4,4)},
 {"name":"Deadline Balance","seq":(1,3,2,1,4,3,4)},{"name":"Priority Chute","seq":(1,2,1,3,4,2,1,4,3,4)},
]
def advance(s,a):
 counts,ages,cursor,served,starve,history,snapshot=s;c=list(counts);ag=list(ages)
 if a==1:c[cursor]=min(4,c[cursor]+1);ag[cursor]=0;cursor=(cursor+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  for i in range(3):
   if c[i]:ag[i]=min(4,ag[i]+1)
  if c[1] or c[2]:starve=(starve+1)%6
  history=(history+(3,))[-8:]
 elif a==4:
  choices=[i for i in (cursor,0,1,2) if c[i]]
  if choices:
   i=choices[0];c[i]-=1;served=(served+(i,))[-6:];ag[i]=0 if c[i]==0 else ag[i];starve=max(0,starve-int(i>0))
  history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(c),tuple(ag),cursor,served,starve,history)
 return tuple(c),tuple(ag),cursor,served,starve,history,snapshot
for x in LEVELS:
 s=((0,0,0),(0,0,0),0,(),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HALL
  colors=(URGENT,ORDINARY,AGE)
  for i,col in enumerate(colors):
   y=9+i*14;f[y:y+8,7:39]=CHUTE;f[y+2:y+6,9:9+g.counts[i]*6]=col
   f[y:y+8,42:47]=AGE;f[y+1:y+7,43:44+g.ages[i]]=col
  f[17:48,50:58]=SERVER;f[20+g.cursor*9:26+g.cursor*9,48:52]=OUTPUT
  for i,v in enumerate(g.served):f[52:57,8+i*7:14+i*7]=colors[v]
  for i in range(g.starve):f[6:9,8+i*5:12+i*5]=STARVE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A051(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a051",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.counts,self.ages,self.cursor,self.served,self.starve,self.history,self.snapshot=((0,0,0),(0,0,0),0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.counts,self.ages,self.cursor,self.served,self.starve,self.history,self.snapshot=advance((self.counts,self.ages,self.cursor,self.served,self.starve,self.history,self.snapshot),a)
  elif a==6:
   if (self.counts,self.ages,self.cursor,self.served,self.starve,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
