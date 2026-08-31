"""a063 Delayed Feedback -- irrigate from a three-turn-old moisture display."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,GREENHOUSE,BED,PLANT,WATER,DISPLAY,LAG,DRY,WET,BAD=7,8,9,10,12,14,11,6,13,15
LEVELS=[
 {"name":"Irrigate Now","seq":(1,)},{"name":"Lagged Display","seq":(1,2)},
 {"name":"Third Turn","seq":(1,2,2)},{"name":"Moving Bed","seq":(3,1,2,2,4)},
 {"name":"Avoid Overwater","seq":(1,2,3,1,2,4,2)},{"name":"Delayed Feedback","seq":(1,2,2,3,1,4,2,1,2,2)},
]
def advance(s,a):
 moisture,displayq,bed,flow,overwater,history,snapshot=s;m=list(moisture);dq=list(displayq)
 if a==1:m[bed]=min(7,m[bed]+2);flow=bed;history=(history+(1,))[-8:]
 elif a==2:
  m=[max(0,x-1) for x in m];dq=(dq+[tuple(m)])[-4:];flow=-1;overwater=(overwater+sum(int(x>5) for x in m))%6;history=(history+(2,))[-8:]
 elif a==3:bed=(bed+1)%3;history=(history+(3,))[-8:]
 elif a==4:m[(bed-1)%3]=max(0,m[(bed-1)%3]-2);dq=(dq+[tuple(m)])[-4:];history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(m),tuple(dq),bed,flow,overwater,history)
 return tuple(m),tuple(dq),bed,flow,overwater,history,snapshot
for x in LEVELS:
 s=((2,4,3),((2,4,3),)*4,0,-1,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;shown=g.displayq[0];f[:,:]=BG;f[4:60,4:60]=GREENHOUSE
  for i,v in enumerate(g.moisture):
   x=7+i*18;f[31:49,x:x+15]=BED;f[22-v*2:30,x+5:x+10]=PLANT;f[45-v*2:48,x+2:x+13]=WATER
   f[12:18,x:x+15]=DISPLAY;f[13:17,x+2:x+2+shown[i]*2]=LAG
   if i==g.bed:f[51:55,x:x+15]=DRY
  if g.flow>=0:x=12+g.flow*18;f[19:26,x:x+6]=WET
  for i in range(g.overwater):f[7:10,43+i*3:46+i*3]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A063(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a063",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.moisture,self.displayq,self.bed,self.flow,self.overwater,self.history,self.snapshot=((2,4,3),((2,4,3),)*4,0,-1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.moisture,self.displayq,self.bed,self.flow,self.overwater,self.history,self.snapshot=advance((self.moisture,self.displayq,self.bed,self.flow,self.overwater,self.history,self.snapshot),a)
  elif a==6:
   if (self.moisture,self.displayq,self.bed,self.flow,self.overwater,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
