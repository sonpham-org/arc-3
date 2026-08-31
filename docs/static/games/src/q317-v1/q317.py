"""q317 Spectrum Ledger -- conserve packets while relational representation changes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PANE,PACKET,STOCK,DOMAIN,RELATION,GOAL,BAD=3,10,9,14,6,11,4,7,15
LEVELS=[{"name":"First Refraction","plan":(1,5)},{"name":"Agent Transfer","plan":(2,4,1,5)},{"name":"Conserved Spectrum","plan":(3,1,2,5)},{"name":"Cross-Domain Stock","plan":(1,4,3,2,5)},{"name":"Relational Return","plan":(2,3,5,4,1,2,5)},{"name":"Spectrum Ledger","plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 stock,domain,relation,integrated=s;stock=list(stock)
 if a in (1,2,3):
  src=a-1;dst=(src+relation+domain)%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:domain=1-domain;stock.reverse();relation=(relation+1)%3
 elif a==5:integrated=(sum((i+1)*v for i,v in enumerate(stock))+domain+relation)%7
 return tuple(stock),domain,relation,integrated
def target(x):
 s=((4,3,2),0,1,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY
  for i,v in enumerate(g.stock):x=8+i*18;f[9:35,x:x+14]=PANE;f[14:28,x+4:x+10]=PACKET-i;f[39:42,x:x+v*3]=STOCK
  f[48:51,8:11+g.domain*22]=DOMAIN;f[53:56,8:11+g.relation*14]=RELATION;f[58:60,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q317(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q317",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.domain=0;self.relation=1;self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stock,self.domain,self.relation,self.integrated=advance((self.stock,self.domain,self.relation,self.integrated),a)
  elif a==6:
   if (self.stock,self.domain,self.relation,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
