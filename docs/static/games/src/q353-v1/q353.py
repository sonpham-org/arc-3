"""q353 Ember Rig -- construct dual-effect kiln tools while assembly and repair share fuel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,PART,RIG,RESOURCE,ROUTE,ACTIVATE,BAD=0,9,8,14,12,11,6,7,15
LEVELS=[{"name":"First Redirect","fuel":5,"plan":(1,4,5)},{"name":"Joined Heat","fuel":6,"plan":(2,1,4,5)},{"name":"Support Vessel","fuel":7,"plan":(3,2,4,1,5)},{"name":"Dual Effect","fuel":8,"plan":(1,3,2,4,5)},{"name":"Fuel Workshop","fuel":10,"plan":(2,1,4,3,4,5)},{"name":"Ember Rig","fuel":12,"plan":(3,1,2,4,3,1,4,5)}]
def advance(s,a):
 parts,rig,heat,route,resource,active=s;parts=list(parts);cost=2 if a==4 else 1
 if resource<cost:return None
 if a in (1,2,3):parts[a-1]+=1;route=(route+a+parts[a-1]+heat)%5
 elif a==4:
  if not sum(parts):return None
  rig+=1;route=(route+parts[0]*2+parts[1]*3+parts[2]+heat)%5;parts=[max(0,v-1) for v in parts];heat=(heat+1)%4
 elif a==5:active+=1;route=(route+rig+active)%5
 resource-=cost
 return tuple(parts),rig,heat,route,resource,active
def target(x):
 s=((0,0,0),0,0,0,x["fuel"],0)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[8:15,8:56]=HEAT
  for i,n in enumerate(g.parts):x=9+i*17;f[19:22,x:x+11]=PART-i;f[24:24+n*6,x:x+11]=PART-i
  for i in range(g.rig):f[41+i*4:44+i*4,10:54]=RIG
  f[51:54,8:11+g.route*10]=ROUTE;f[55:58,8:11+g.resource*4]=RESOURCE;f[58:60,48:56]=ACTIVATE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q353(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q353",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.parts=(0,0,0);self.rig=self.heat=self.route=self.active=0;self.resource=x["fuel"]
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.heat,self.route,self.resource,self.active),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.heat,self.route,self.resource,self.active=s
  elif a==6:
   if (self.parts,self.rig,self.heat,self.route,self.resource,self.active)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
