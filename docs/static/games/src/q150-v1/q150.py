"""q150 Minimum Regret -- preserve the route with the smallest worst-case loss."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MAP,ROUTE,LOSS,SAMPLE,FALLBACK,COMMIT,GOAL,BAD=3,10,9,14,6,11,4,7,15
def plan(losses,extra=()):return (1,2,3)+tuple(extra)+(min(range(3),key=lambda i:max(losses[i]))+1,4,5)
LEVELS=[{"name":"Safe Branch","losses":((1,2),(2,4),(1,5)),"plan":plan(((1,2),(2,4),(1,5)))},{"name":"Changed Risk","losses":((2,6),(2,3),(1,5)),"plan":plan(((2,6),(2,3),(1,5)))},{"name":"Equal Means","losses":((1,7),(3,4),(2,6)),"plan":plan(((1,7),(3,4),(2,6)),(1,))},{"name":"Recoverable Detour","losses":((3,5),(1,8),(2,4)),"plan":plan(((3,5),(1,8),(2,4)),(2,1))},{"name":"Worst-Case Trap","losses":((1,9),(4,6),(3,5)),"plan":plan(((1,9),(4,6),(3,5)),(1,2,))},{"name":"Minimum Regret","losses":((5,7),(2,8),(4,6)),"plan":plan(((5,7),(2,8),(4,6)),(3,1,2))}]
def advance(s,a,x):
 observations,selected,fallback,committed=s;observations=list(observations)
 if a in (1,2,3):selected=a-1;seen=sum(1 for r,_ in observations if r==selected);out=x["losses"][selected][seen%2];observations.append((selected,out))
 elif a==4:
  if len({r for r,_ in observations})<3:return None
  fallback=tuple(sorted((max(v),i) for i,v in enumerate(x["losses"])))
 elif a==5:
  best=min(range(3),key=lambda i:max(x["losses"][i]))
  if fallback is None or selected!=best:return None
  committed=(best,tuple(observations),fallback)
 return tuple(observations),selected,fallback,committed
def target(x):
 s=((),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAP
  for i in range(3):x=8+i*18;f[8:32,x:x+14]=ROUTE;f[25:29,x+3:x+11]=LOSS-i
  for i,(r,v) in enumerate(g.observations[-8:]):x=8+(i%4)*12;y=36+(i//4)*8;f[y:y+5,x:x+3+v]=SAMPLE-r
  f[52:55,8:24]=FALLBACK if g.fallback else ROUTE;f[56:59,44:56]=COMMIT if g.committed else GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q150(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q150",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.observations=();self.selected=0;self.fallback=self.committed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.observations,self.selected,self.fallback,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.observations,self.selected,self.fallback,self.committed=s
  elif a==6:
   if (self.observations,self.selected,self.fallback,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
