"""q447 Canopy Lineage -- preserve ancestry while a narrow orchard store reorders tokens."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,SEED,STORE,TRAIL,SELECT,GATE,BAD=8,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Stored Split","ancestor":1,"capacity":2,"plan":(1,4,5)},{"name":"Merged Bin","ancestor":2,"capacity":2,"plan":(3,1,4,2,4,5)},{"name":"Three Terraces","ancestor":3,"capacity":2,"plan":(1,2,3,4,4,4,5)},{"name":"Branch Return","ancestor":2,"capacity":2,"plan":(3,1,4,2,1,4,5)},{"name":"Appearance Store","ancestor":1,"capacity":3,"plan":(1,3,2,4,5)},{"name":"Canopy Lineage","ancestor":3,"capacity":3,"plan":(3,1,2,4,3,4,1,4,5)}]
def advance(s,a,x):
 buffer,store,selection,failed,committed=s;buffer=list(buffer);store=list(store)
 if a==1:
  if len(buffer)>=x["capacity"]:return None
  anc,look=buffer[0];buffer.append((anc,(look+1+len(store))%4))
 elif a==2:
  if len(buffer)<2:
   if not store:return None
   buffer.append(store.pop())
  buffer=[(buffer[0][0],(buffer[0][1]+buffer[1][1])%4)]+buffer[2:]
 elif a==3:buffer=[(anc,(look+1)%4) for anc,look in buffer]
 elif a==4:
  store.extend(buffer);selection=(selection+1)%4;failed=(selection,tuple(store[-3:]));buffer=[(x["ancestor"],(selection+len(store))%4)]
 elif a==5:
  if failed is None or selection!=x["ancestor"]:return None
  committed=(selection,len(store),sum(v for _,v in store)%4)
 return tuple(buffer),tuple(store),selection,failed,committed
def target(x):
 s=(((x["ancestor"],0),),(),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD;f[8:31,7:29]=SHADE;f[8:31,35:57]=STORE
  for i,(anc,look) in enumerate(g.buffer[:3]):f[11+i*7:16+i*7,11:18]=SEED-look;f[17+i*7:19+i*7,11:13+anc]=TRAIL
  for i,(anc,look) in enumerate(g.store[-6:]):x=39+(i%2)*8;y=11+(i//2)*7;f[y:y+5,x:x+6]=SEED-look
  f[38:41,8:11+g.selection*11]=SELECT;f[48:51,8:24]=TRAIL;f[54:57,40:56]=GATE if g.committed else STORE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q447(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(1);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q447",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,ancestor):self.buffer=((ancestor,0),);self.store=();self.selection=0;self.failed=self.committed=None
 def on_set_level(self,l):self._reset(LEVELS[self.level_index]["ancestor"]);self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buffer,self.store,self.selection,self.failed,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.buffer,self.store,self.selection,self.failed,self.committed=s
  elif a==6:
   if (self.buffer,self.store,self.selection,self.failed,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
