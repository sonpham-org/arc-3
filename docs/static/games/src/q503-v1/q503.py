"""q503 Ember Frame -- compose local vessel motion with heat bands under one shared resource."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,FRAME,RESOURCE,EVIDENCE,GOAL,BAD=13,12,8,14,9,11,10,0,15
LEVELS=[{"name":"Local Ember","budget":4,"plan":(1,5)},{"name":"Translated Kiln","budget":6,"plan":(2,4,1,5)},{"name":"Rotated Band","budget":7,"plan":(3,1,2,5)},{"name":"Shared Fuel","budget":9,"plan":(1,4,3,2,5,1)},{"name":"Repair Tradeoff","budget":10,"plan":(2,3,5,4,1,2,5)},{"name":"Ember Frame","budget":12,"plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 vessels,rotation,offset,evidence,resource=s;vessels=list(vessels)
 if resource<=0:return None
 if a in (1,2):i=(a-1+rotation)%3;vessels[i]=(vessels[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:rotation=(rotation+1)%4;vessels=vessels[1:]+vessels[:1]
 elif a==4:offset=(offset+1)%5;vessels=[(v+offset)%5 for v in vessels]
 elif a==5:evidence|=1<<((sum(vessels)+rotation+offset)%3)
 resource-=1
 return tuple(vessels),rotation,offset,evidence,resource
def target(x):
 s=((0,2,4),0,0,0,x["budget"])
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=KILN
  for i,v in enumerate(g.vessels):x=8+i*18;f[10:42,x:x+13]=HEAT;f[14+v*5:20+v*5,x+3:x+10]=VESSEL
  f[44:47,8:8+g.rotation*11]=FRAME;f[49:52,8:8+g.resource*4]=RESOURCE
  for i in range(3):f[55:59,8+i*15:19+i*15]=EVIDENCE if g.evidence&(1<<i) else GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q503(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q503",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.vessels=(0,2,4);self.rotation=self.offset=self.evidence=0;self.resource=x["budget"]
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.vessels,self.rotation,self.offset,self.evidence,self.resource),a)
   if s is None:self.bad=True;self.lose()
   else:self.vessels,self.rotation,self.offset,self.evidence,self.resource=s
  elif a==6:
   if (self.vessels,self.rotation,self.offset,self.evidence,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
