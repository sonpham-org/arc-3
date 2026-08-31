"""q446 Palimpsest Lineage -- recover ancestry through split, merge, and failed exemplars."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,TRAIL,SELECT,EXAMPLE,GATE,BAD=8,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Split Clue","ancestor":1,"plan":(1,4,5)},{"name":"Merged Copy","ancestor":2,"plan":(3,1,4,2,4,5)},{"name":"Three Errata","ancestor":3,"plan":(1,2,3,4,4,4,5)},{"name":"Branch Return","ancestor":2,"plan":(3,1,4,2,1,4,5)},{"name":"Appearance Trap","ancestor":1,"plan":(1,3,2,4,5)},{"name":"Palimpsest Lineage","ancestor":3,"plan":(3,1,2,4,3,4,1,4,5)}]
def advance(s,a,x):
 tokens,selection,failed,committed=s;tokens=list(tokens)
 if a==1:
  anc,look=tokens[0];tokens.extend(((anc,(look+1)%4),(anc,(look+2)%4)))
 elif a==2:
  if len(tokens)>1:tokens=[(tokens[0][0],(tokens[0][1]+tokens[1][1])%4)]+tokens[2:]
 elif a==3:tokens=[(anc,(look+1)%4) for anc,look in tokens]
 elif a==4:selection=(selection+1)%4;failed=(selection,tuple(tokens[:3]))
 elif a==5:
  if failed is None:return None
  committed=(selection,failed,len(tokens),sum(v for _,v in tokens)%4)
 return tuple(tokens),selection,failed,committed
def target(x):
 s=(((x["ancestor"],0),),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE;f[8:35,7:57]=SHELF
  for i,(anc,look) in enumerate(g.tokens[:10]):x=9+(i%5)*10;y=11+(i//5)*11;f[y:y+7,x:x+7]=TILE-look;f[y+7:y+9,x:x+2+anc]=TRAIL
  f[40:43,8:11+g.selection*12]=SELECT;f[48:51,8:24]=EXAMPLE if g.failed else TRAIL;f[55:58,40:56]=GATE if g.committed else SHELF
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q446(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(1);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q446",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,ancestor):self.tokens=((ancestor,0),);self.selection=0;self.failed=self.committed=None
 def on_set_level(self,l):self._reset(LEVELS[self.level_index]["ancestor"]);self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.selection,self.failed,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.selection,self.failed,self.committed=s
  elif a==6:
   if (self.tokens,self.selection,self.failed,self.committed)==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
