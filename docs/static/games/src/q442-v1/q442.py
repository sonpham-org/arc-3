"""q442 Tide Lineage -- preserve shell ancestry before an irreversible gate commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,TRAIL,SELECT,COMMIT,TARGET,BAD=8,10,9,14,12,5,11,6,15
LEVELS=[{"name":"First Split","ancestor":1,"plan":(1,4,5)},{"name":"Appearance Current","ancestor":2,"plan":(3,1,4,2,4,5)},{"name":"Merged Tide","ancestor":3,"plan":(1,2,3,4,4,4,5)},{"name":"One-Way Gate","ancestor":2,"plan":(3,1,4,2,1,4,5)},{"name":"Causal Return","ancestor":1,"plan":(1,3,2,4,5)},{"name":"Tide Lineage","ancestor":3,"plan":(3,1,2,4,3,4,1,4,5)}]
def advance(s,a):
 tokens,current,direction,selection,committed=s;t=[list(x) for x in tokens]
 if committed:return None
 if a==1:
  m,c=t.pop(0);t.extend([[m,(c+1+current)%4],[m,(c+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1]+current)%4])
 elif a==3:
  colors=[x[1] for x in t][1:]+[t[0][1]]
  for x,c in zip(t,colors):x[1]=c
 elif a==4:
  current=(current+direction)%3
  if current in (0,2):direction=-direction
  t.reverse();selection=(selection+1)%4
 elif a==5:committed=True
 return tuple((x[0],x[1]) for x in t),current,direction,selection,committed
def target(x):
 s=(((1,0),(2,1),(4,2)),0,1,0,False)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:15,8:56]=CURRENT
  for i,(mask,color) in enumerate(g.tokens):px=6+i*11;f[20:31,px:px+9]=SHELL-color%3;f[34:37,px:px+min(mask,7)*2]=TRAIL
  f[44:47,8:11+g.current*14]=CURRENT;f[50:53,8:11+g.selection*12]=SELECT;f[55:58,8:11+x["ancestor"]*12]=TARGET;f[58:60,49:56]=COMMIT if g.committed else CURRENT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q442(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q442",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tokens=((1,0),(2,1),(4,2));self.current=self.selection=0;self.direction=1;self.committed=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.current,self.direction,self.selection,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.current,self.direction,self.selection,self.committed=s
  elif a==6:
   if (self.tokens,self.current,self.direction,self.selection,self.committed)==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
