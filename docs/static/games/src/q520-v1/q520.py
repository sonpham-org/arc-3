"""q520 Vault Frame -- route two conserved echoes through a moving local passage frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,CHAMBER,A_ECHO,B_ECHO,FRAME,CAPACITY,GOAL,BAD=0,11,9,14,10,12,6,13,15
LEVELS=[
 {"name":"First Echo","seq":(1,)},{"name":"Paired Echo","seq":(1,2)},
 {"name":"Rotated Passage","seq":(3,4,1)},{"name":"Moving Vault","seq":(1,2,3,1,2)},
 {"name":"Shared Capacity","seq":(3,4,1,2,3,1)},{"name":"Vault Frame","seq":(1,2,3,4,1,3,4,3)}]
def advance(s,a,x):
 boxes,frame,goal=s;b=[list(v) for v in boxes]
 if a in (1,2):
  q=a-1;src,dst=frame,(frame+1)%3
  if not b[src][q] or sum(b[dst])>=4:return None
  b[src][q]-=1;b[dst][q]+=1
 elif a==3:frame=(frame+1)%3
 elif a==4:b[frame],b[(frame+2)%3]=b[(frame+2)%3],b[frame]
 elif a==5:
  if (tuple(map(tuple,b)),frame)!=x["target"]:return None
  goal=(tuple(map(tuple,b)),frame)
 return tuple(map(tuple,b)),frame,goal
for x in LEVELS:
 s=(((2,1),(0,1),(1,0)),0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["target"]=(s[0],s[1]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(((2,1),(0,1),(1,0)),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  for i,(a,b) in enumerate(g.boxes):
   x=8+i*17;f[8:34,x:x+14]=CHAMBER;f[28-a*5:28,x+2:x+6]=A_ECHO;f[28-b*5:28,x+8:x+12]=B_ECHO
  f[39:43,8:8+g.frame*15]=FRAME;f[47:51,8:56]=CAPACITY
  if g.goal:f[54:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q520(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q520",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.boxes=((2,1),(0,1),(1,0));self.frame=0;self.goal=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.boxes,self.frame,self.goal),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.boxes,self.frame,self.goal=s
  elif a==6:
   if (self.boxes,self.frame,self.goal)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
