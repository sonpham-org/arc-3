"""q509 Strata Frame -- undo physical quarry probes while retaining their knowledge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,CRAWLER,FRAME,KNOWLEDGE,PROBE,UNDO,BAD=9,10,12,14,5,11,6,7,15
LEVELS=[{"name":"Persistent Sample","plan":(4,5)},{"name":"Local Crawler","plan":(1,4,5)},{"name":"Rotated Fault","plan":(3,2,4,5)},{"name":"Reversible Probe","plan":(1,4,2,5)},{"name":"Knowledge Remains","plan":(2,3,4,1,5)},{"name":"Strata Frame","plan":(3,1,4,2,5,1)}]
def advance(s,a):
 crawlers,rotation,offset,knowledge,snapshot,undos=s;crawlers=list(crawlers)
 if a in (1,2):i=(a-1+rotation)%3;crawlers[i]=(crawlers[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:rotation=(rotation+1)%4;crawlers=crawlers[1:]+crawlers[:1]
 elif a==4:
  if snapshot is None:snapshot=(tuple(crawlers),rotation,offset)
  observed=(sum(crawlers)+rotation+offset)%4;knowledge|=1<<observed;offset=(offset+1)%5;crawlers=[(v+offset+rotation)%5 for v in crawlers]
 elif a==5:
  if snapshot is not None:crawlers,rotation,offset=snapshot;snapshot=None;undos+=1
 return tuple(crawlers),rotation,offset,knowledge,snapshot,undos
def target(x):
 s=((0,2,4),0,0,0,None,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY;f[8:15,8:56]=FAULT
  for i,v in enumerate(g.crawlers):x=8+i*18;f[20:39,x:x+14]=FAULT;f[24+v*3:29+v*3,x+3:x+11]=CRAWLER-i
  f[43:46,8:11+g.rotation*11]=FRAME
  for i in range(4):f[49:53,8+i*12:17+i*12]=KNOWLEDGE if g.knowledge&(1<<i) else QUARRY
  f[55:58,8:20]=PROBE if g.snapshot is not None else UNDO;f[58:60,48:56]=UNDO
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q509(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q509",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.crawlers=(0,2,4);self.rotation=self.offset=self.knowledge=self.undos=0;self.snapshot=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.crawlers,self.rotation,self.offset,self.knowledge,self.snapshot,self.undos=advance((self.crawlers,self.rotation,self.offset,self.knowledge,self.snapshot,self.undos),a)
  elif a==6:
   if (self.crawlers,self.rotation,self.offset,self.knowledge,self.snapshot,self.undos)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
