"""q717 Canopy Gradient -- route conserved seeds through a capacity-limited store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,SEED,STORE,SEASON,OBSERVE,COMMIT,BAD=14,7,11,6,2,9,4,13,15
LEVELS=[
 {"name":"One Transfer","initial":(2,0,0),"cap":1,"threshold":3,"plan":(1,2,4,5)},
 {"name":"Two Stored Seeds","initial":(2,0,0),"cap":2,"threshold":4,"plan":(1,1,2,2,4,5)},
 {"name":"Seasonal Gradient","initial":(2,0,0),"cap":1,"threshold":4,"plan":(3,1,2,4,5)},
 {"name":"Narrow Ordering","initial":(2,0,0),"cap":1,"threshold":4,"plan":(1,2,1,2,4,5)},
 {"name":"Split Distribution","initial":(3,0,0),"cap":1,"threshold":6,"plan":(1,2,3,1,2,4,5)},
 {"name":"Canopy Gradient","initial":(4,0,0),"cap":2,"threshold":9,"plan":(1,1,2,3,2,1,2,4,5)}]
def influence(bins):return bins[0]+2*bins[1]+3*bins[2]
def advance(s,a,x):
 bins,store,season,observed,committed=s;bins=list(bins);store=list(store)
 if committed is not None:return None
 if a==1:
  if bins[0]<=0 or len(store)>=x["cap"]:return None
  bins[0]-=1;store.append(1)
 elif a==2:
  if not store:return None
  store.pop(0);bins[1+season%2]+=1
 elif a==3:season^=1
 elif a==4:observed=influence(bins)
 elif a==5:
  now=influence(bins)
  if observed!=now or now<x["threshold"]:return None
  committed=(tuple(bins),tuple(store),season,now)
 return tuple(bins),tuple(store),season,observed,committed
def target(x):
 s=(x["initial"],(),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD
  for i,v in enumerate(g.bins):x=8+i*17;f[8:35,x:x+13]=SHADE+i%2;f[31-v*5:33,x+2:x+11]=SEED+i
  for i in range(len(g.store)):f[40:46,9+i*13:19+i*13]=STORE
  f[48:51,8:8+g.season*13]=SEASON;f[53:56,8:56]=OBSERVE
  if g.committed:f[38:58,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q717(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q717",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.store=();self.season=0;self.observed=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.store,self.season,self.observed,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.store,self.season,self.observed,self.committed=s
  elif a==6:
   if (self.bins,self.store,self.season,self.observed,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
