"""q352 Tide Rig -- assemble a dual-effect device before its irreversible launch."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CHANNEL,PART,RIG,CURRENT,ROUTE,LAUNCH,BAD=5,10,9,14,12,6,11,7,15
LEVELS=[{"name":"First Redirect","plan":(1,4,5)},{"name":"Joined Current","plan":(2,1,4,5)},{"name":"Support Channel","plan":(3,2,4,1,5)},{"name":"Dual Effect","plan":(1,3,2,4,5)},{"name":"One-Way Launch","plan":(2,1,4,3,4,5)},{"name":"Tide Rig","plan":(3,1,2,4,3,1,4,5)}]
def advance(s,a):
 parts,rig,current,direction,route,launched=s;parts=list(parts)
 if launched:return None
 if a in (1,2,3):parts[a-1]+=1;route=(route+a+parts[a-1]+current)%5
 elif a==4:
  if not sum(parts):return None
  rig+=1;route=(route+parts[0]*2+parts[1]*3+parts[2]+direction)%5;parts=[max(0,v-1) for v in parts]
  current=(current+direction)%3
  if current in (0,2):direction=-direction
 elif a==5:launched=True;route=(route+rig+current)%5
 return tuple(parts),rig,current,direction,route,launched
def target(x):
 s=((0,0,0),0,0,1,0,False)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:15,8:56]=CHANNEL
  for i,n in enumerate(g.parts):x=9+i*17;f[19:22,x:x+11]=PART-i;f[24:24+n*6,x:x+11]=PART-i
  for i in range(g.rig):f[41+i*4:44+i*4,10:54]=RIG
  f[51:54,8:11+g.current*14]=CURRENT;f[56:59,8:11+g.route*10]=ROUTE;f[58:60,48:56]=LAUNCH if g.launched else CHANNEL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q352(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q352",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.rig=self.current=self.route=0;self.direction=1;self.launched=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.current,self.direction,self.route,self.launched),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.current,self.direction,self.route,self.launched=s
  elif a==6:
   if (self.parts,self.rig,self.current,self.direction,self.route,self.launched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
