"""a118 Bottleneck Match -- minimize the slowest carrier-task completion time."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,DEPOT,CARRIER,TASK,ROUTE,CURSOR,FAST,SLOW,MAXIMUM,TIE=15,8,12,10,9,13,4,6,14,11
BAD=7
TIMES=((2,5,7,9,6),(6,2,5,8,7),(7,4,2,6,9),(9,7,5,2,4),(5,8,7,4,2))
LEVELS=[
 {"name":"Assign Task","seq":(1,)},{"name":"Select Carrier","seq":(2,)},
 {"name":"Swap Tasks","seq":(3,1)},{"name":"Launch Together","seq":(1,2,3,4,2)},
 {"name":"Reduce Maximum","seq":(1,3,2,1,4,3,2)},{"name":"Bottleneck Match","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 assignments,cursor,max_time,total,ties,history,snapshot=s;ass=list(assignments)
 if a==1:ass[cursor]=(ass[cursor]+1)%5;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:
  j=(cursor+1)%5;ass[cursor],ass[j]=ass[j],ass[cursor];history=(history+(3,))[-8:]
 elif a==4:
  values=[TIMES[i][task] for i,task in enumerate(ass)];max_time=max(values);total=sum(values);ties=values.count(max_time);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(ass),cursor,max_time,total,ties,history)
 return tuple(ass),cursor,max_time,total,ties,history,snapshot
for x in LEVELS:
 s=((0,1,2,3,4),0,2,10,5,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DEPOT
  for i,task in enumerate(g.assignments):
   y=11+i*9;f[y:y+6,8:14]=CARRIER;tx=49;ty=11+task*9;f[ty:ty+6,tx:tx+6]=TASK;f[min(y+2,ty+2):max(y+3,ty+3),14:49]=ROUTE
   t=TIMES[i][task];f[y+1:y+5,16:16+min(25,t*3)]=SLOW if t==g.max_time else FAST
   if i==g.cursor:f[y-3:y,7:15]=CURSOR
  f[54:58,8:8+min(10,g.max_time)*5]=MAXIMUM;f[7:10,8:8+g.ties*8]=TIE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A118(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a118",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.assignments,self.cursor,self.max_time,self.total,self.ties,self.history,self.snapshot=((0,1,2,3,4),0,2,10,5,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.assignments,self.cursor,self.max_time,self.total,self.ties,self.history,self.snapshot=advance((self.assignments,self.cursor,self.max_time,self.total,self.ties,self.history,self.snapshot),a)
  elif a==6:
   if (self.assignments,self.cursor,self.max_time,self.total,self.ties,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
