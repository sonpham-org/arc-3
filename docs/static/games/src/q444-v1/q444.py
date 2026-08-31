"""q444 Honeycomb Lineage -- trace courier ancestry across local and enclosing cycles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,TRAIL,SELECT,LOCAL,GLOBAL,BAD=13,9,14,5,11,4,6,7,15
LEVELS=[{"name":"First Split","cycle":2,"ancestor":1,"plan":(1,4,5)},{"name":"Appearance Cell","cycle":2,"ancestor":2,"plan":(3,1,4,2,4,5)},{"name":"Merged Nectar","cycle":3,"ancestor":3,"plan":(1,2,3,4,4,4,5)},{"name":"Two-Clock Trail","cycle":3,"ancestor":2,"plan":(3,1,4,2,1,4,5)},{"name":"Nested Identity","cycle":4,"ancestor":1,"plan":(1,3,2,4,5)},{"name":"Honeycomb Lineage","cycle":4,"ancestor":3,"plan":(3,1,2,4,3,4,1,4,5)}]
def advance(s,a,x):
 tokens,local,global_,selection,committed=s;t=[list(v) for v in tokens]
 if committed:return None
 if a==1:
  m,c=t.pop(0);t.extend([[m,(c+1+global_)%4],[m,(c+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1]+global_)%4])
 elif a==3:
  colors=[v[1] for v in t][1:]+[t[0][1]]
  for v,c in zip(t,colors):v[1]=c
 elif a==4:t.reverse();selection=(selection+1)%4
 elif a==5:committed=True
 local+=1
 if local>=x["cycle"]:local=0;global_=(global_+1)%4
 return tuple((v[0],v[1]) for v in t),local,global_,selection,committed
def target(x):
 s=(((1,0),(2,1),(4,2)),0,0,0,False)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=APIARY;f[8:15,8:56]=CELL
  for i,(mask,color) in enumerate(g.tokens):px=6+i*11;f[20:31,px:px+9]=COURIER+color%3;f[34:37,px:px+min(mask,7)*2]=TRAIL
  f[44:47,8:11+g.selection*12]=SELECT;f[50:53,8:11+x["ancestor"]*12]=TRAIL;f[54:57,8:11+g.local*11]=LOCAL;f[58:60,8:11+g.global_*11]=GLOBAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q444(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q444",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tokens=((1,0),(2,1),(4,2));self.local=self.global_=self.selection=0;self.committed=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.local,self.global_,self.selection,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.local,self.global_,self.selection,self.committed=s
  elif a==6:
   if (self.tokens,self.local,self.global_,self.selection,self.committed)==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
