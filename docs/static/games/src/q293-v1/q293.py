"""q293 Ember Ledger -- conserve vessel stock while every operation burns shared fuel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,STOCK,RESOURCE,REPAIR,GOAL,BAD=14,9,8,12,5,11,6,7,15
LEVELS=[{"name":"First Pour","fuel":4,"plan":(1,5)},{"name":"Heated Transfer","fuel":6,"plan":(2,4,1,5)},{"name":"Conserved Clay","fuel":7,"plan":(3,1,2,5)},{"name":"Shared Fuel","fuel":9,"plan":(1,4,3,2,5,1)},{"name":"Repair Tradeoff","fuel":10,"plan":(2,3,5,4,1,2,5)},{"name":"Ember Ledger","fuel":12,"plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 stock,heat,resource,repairs=s;stock=list(stock)
 if resource<=0:return None
 if a in (1,2,3):
  src=a-1;dst=(src+heat+1)%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:heat=(heat+1)%3;stock=stock[1:]+stock[:1]
 elif a==5:repairs+=1;heat=(heat+repairs)%3
 resource-=1
 return tuple(stock),heat,resource,repairs
def target(x):
 s=((4,3,2),0,x["fuel"],0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:15,8:56]=HEAT
  for i,v in enumerate(g.stock):x=9+i*18;f[20:36,x:x+12]=VESSEL-i;f[39:42,x:x+v*3]=STOCK
  f[48:51,8:11+g.heat*14]=HEAT;f[54:57,8:11+g.resource*4]=RESOURCE;f[58:60,8:20]=REPAIR;f[58:60,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q293(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q293",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.stock=(4,3,2);self.heat=self.repairs=0;self.resource=x["fuel"]
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.heat,self.resource,self.repairs),a)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.heat,self.resource,self.repairs=s
  elif a==6:
   if (self.stock,self.heat,self.resource,self.repairs)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
