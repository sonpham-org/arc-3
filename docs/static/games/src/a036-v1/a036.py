"""a036 Stable Sorter -- sort by size without reversing equal-size arrival order."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DEPOT,CRATE,SIZE,ARRIVAL,COMPARATOR,EXIT,GOAL,BAD=5,10,14,8,11,6,12,13,15
LEVELS=[{"name":"First Compare","seq":(1,)},{"name":"Advance Pair","seq":(2,1)},{"name":"Reveal Arrival","seq":(3,1,2)},{"name":"Network Pass","seq":(4,2,1,3)},{"name":"Stable Ties","seq":(2,3,1,4,2,1)},{"name":"Stable Sorter","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 crates,index,revealed,history,passes,sorted_out=s;c=list(crates)
 if a==1:
  i=index%(len(c)-1)
  if c[i][0]>c[i+1][0]:c[i],c[i+1]=c[i+1],c[i]
  history=history+((i,tuple(c)),)
 elif a==2:index=(index+1)%(len(c)-1)
 elif a==3:revealed=revealed+((index,c[index][1]),)
 elif a==4:
  for i in range(len(c)-1):
   if c[i][0]>c[i+1][0]:c[i],c[i+1]=c[i+1],c[i]
  passes+=1
 elif a==5:sorted_out=(tuple(c),index,revealed[-4:],history[-4:],passes)
 return tuple(c),index,revealed,history,passes,sorted_out
for x in LEVELS:
 s=(((2,0),(1,1),(2,2),(1,3),(3,4)),0,(),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DEPOT
  for i,(size,arrival) in enumerate(g.crates):x=7+i*11;f[25-size*5:30,x:x+9]=CRATE;f[27-size*5:30-size*5,x+2:x+7]=SIZE;f[31:34,x:x+2+arrival]=ARRIVAL
  f[37:43,7+g.index*11:27+g.index*11]=COMPARATOR
  for i,_ in enumerate(g.revealed[-4:]):f[47:52,8+i*12:17+i*12]=EXIT
  if g.sorted_out:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A036(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a036",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.crates=((2,0),(1,1),(2,2),(1,3),(3,4));self.index=0;self.revealed=self.history=();self.passes=0;self.sorted_out=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.crates,self.index,self.revealed,self.history,self.passes,self.sorted_out=advance((self.crates,self.index,self.revealed,self.history,self.passes,self.sorted_out),a)
  elif a==6:
   if (self.crates,self.index,self.revealed,self.history,self.passes,self.sorted_out)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
