"""q416 Palimpsest Revision -- revise a drifting archive rule from explicit failed examples."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,WEAR,RULE,EXAMPLE,REPAIR,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"First Correction","rule":1,"plan":(1,4,5)},{"name":"Delayed Ink","rule":2,"plan":(2,1,4,5)},{"name":"Rewritten Shelf","rule":3,"plan":(3,2,4,1,5)},{"name":"Compound Revision","rule":1,"plan":(1,3,2,4,5)},{"name":"Second Erratum","rule":2,"plan":(2,1,4,3,4,5)},{"name":"Palimpsest Revision","rule":3,"plan":(3,1,2,4,3,1,4,5)}]
def advance(s,a,x):
 tiles,wear,delay,failed,repairs=s;tiles=list(tiles)
 if a in (1,2,3):
  i=a-1;tiles[i]=(tiles[i]+a+x["rule"]+wear+delay)%5;wear=(wear+1)%4
 elif a==4:failed=(tuple(tiles),wear,(x["rule"]+wear+delay)%4);wear=(wear+1)%4
 elif a==5:
  if failed is None:return None
  delay=(delay+failed[2]+1)%4;tiles=tiles[1:]+tiles[:1];repairs+=1
 return tuple(tiles),wear,delay,failed,repairs
def target(x):
 s=((0,2,4),0,0,None,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE
  for i,v in enumerate(g.tiles):x=8+i*18;f[9:37,x:x+14]=SHELF;f[13+v*4:19+v*4,x+4:x+10]=TILE-i
  f[41:44,8:11+g.wear*11]=WEAR;f[47:50,8:11+g.delay*11]=RULE;f[53:56,8:24]=EXAMPLE if g.failed else SHELF;f[57:60,40:43+g.repairs*3]=REPAIR
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q416(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q416",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tiles=(0,2,4);self.wear=self.delay=self.repairs=0;self.failed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tiles,self.wear,self.delay,self.failed,self.repairs),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.tiles,self.wear,self.delay,self.failed,self.repairs=s
  elif a==6:
   if (self.tiles,self.wear,self.delay,self.failed,self.repairs)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
