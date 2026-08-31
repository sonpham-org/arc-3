"""q730 Vault Gradient -- route two conserved quantities through shared-capacity chambers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,CHAMBER,A_ECHO,B_ECHO,CAPACITY,PHASE,GOAL,BAD=7,11,9,14,10,12,6,13,15
LEVELS=[
 {"name":"First Pair","initial":((2,1),(0,1),(1,0)),"seq":(1,2)},{"name":"Double Pair","initial":((3,1),(0,2),(1,0)),"seq":(1,1,2,2)},
 {"name":"Capacity Gate","initial":((3,2),(0,2),(1,0)),"seq":(4,1,1,2,2)},{"name":"Dual Gradient","initial":((4,2),(0,2),(1,0)),"seq":(4,1,2,3,4,1,2)},
 {"name":"Phase Routing","initial":((4,3),(0,2),(1,0)),"seq":(4,1,1,2,3,4,1,2)},{"name":"Vault Gradient","initial":((5,3),(0,3),(1,0)),"seq":(4,1,2,4,1,2,3,4,1,2)}]
def advance(s,a,x):
 boxes,capacity,phase,done=s;b=[list(v) for v in boxes]
 if a in (1,2):
  q=a-1;src,dst=(0,1) if q==0 else (1,2)
  if not b[src][q] or sum(b[dst])>=capacity:return None
  b[src][q]-=1;b[dst][q]+=1
 elif a==3:b=b[-1:]+b[:-1];phase=(phase+1)%3
 elif a==4:capacity+=1;phase=(phase+1)%3
 elif a==5:
  if (tuple(map(tuple,b)),capacity,phase)!=x["goal"]:return None
  done=x["goal"]
 return tuple(map(tuple,b)),capacity,phase,done
for x in LEVELS:
 s=(x["initial"],4,0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=(s[0],s[1],s[2]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(x["initial"],4,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  for i,(a,b) in enumerate(g.boxes):
   x=8+i*17;f[8:33,x:x+14]=CHAMBER;f[29-a*3:29,x+2:x+6]=A_ECHO;f[29-b*3:29,x+8:x+12]=B_ECHO
  f[39:43,8:8+g.capacity*7]=CAPACITY;f[47:51,8:8+g.phase*15]=PHASE
  if g.done:f[54:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q730(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q730",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.boxes=self.cfg["initial"];self.capacity=4;self.phase=0;self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.boxes,self.capacity,self.phase,self.done),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.boxes,self.capacity,self.phase,self.done=s
  elif a==6:
   if (self.boxes,self.capacity,self.phase,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
